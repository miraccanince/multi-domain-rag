"""
FastAPI Backend for RAG Documentation Assistant

This API provides RESTful endpoints for:
- Question answering with LLM (streaming)
- Document search and retrieval
- Domain management
- System health monitoring

Usage:
    uvicorn api.main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import json
import chromadb
from pathlib import Path
from datetime import datetime
import sys
import time
import shutil
import subprocess

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.qa_chain import ask_question, warm_up_model, generate_answer_ollama
from src.hybrid_search import HybridSearchEngine
from src.cache_manager import get_query_cache, get_performance_monitor
from src.feedback_manager import get_feedback_manager

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize FastAPI app
app = FastAPI(
    title="RAG Documentation Assistant API",
    description="Retrieval-Augmented Generation API for document Q&A",
    version="1.0.0"
)

# Add rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
chroma_client = None
collection = None
hybrid_engine = None


# Request/Response Models
class QueryRequest(BaseModel):
    question: str = Field(..., description="User's question", min_length=1)
    domain: Optional[str] = Field(None, description="Filter by domain (automotive/fashion)")
    n_results: int = Field(3, description="Number of results to retrieve", ge=1, le=10)
    search_method: str = Field("hybrid", description="Search method: semantic, bm25, or hybrid")
    use_reranking: bool = Field(True, description="Use LLM reranking")
    use_cache: bool = Field(True, description="Use query caching")
    stream: bool = Field(True, description="Stream LLM response")


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query", min_length=1)
    domain: Optional[str] = Field(None, description="Filter by domain")
    n_results: int = Field(5, description="Number of results", ge=1, le=20)
    search_method: str = Field("hybrid", description="Search method")


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: List[Dict[str, Any]]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    results: List[Dict[str, Any]]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    ollama_running: bool
    database_ready: bool
    documents_indexed: int
    cache_size: int
    performance_stats: Dict[str, Any]


class DomainResponse(BaseModel):
    domains: List[Dict[str, Any]]


class FeedbackRequest(BaseModel):
    question: str = Field(..., description="The question that was asked")
    answer: str = Field(..., description="The answer that was given")
    rating: int = Field(..., description="User rating: 1 (thumbs up) or -1 (thumbs down)")
    comment: Optional[str] = Field(None, description="Optional user comment")
    domain: Optional[str] = Field(None, description="Domain used for query")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


# Startup/Shutdown Events
@app.on_event("startup")
async def startup_event():
    """Initialize ChromaDB and warm up the model."""
    global chroma_client, collection, hybrid_engine

    print("🚀 Starting RAG API server...")

    # Initialize ChromaDB
    db_path = Path(__file__).parent.parent / "chroma_db"
    chroma_client = chromadb.PersistentClient(path=str(db_path))
    collection = chroma_client.get_or_create_collection(name="documents")

    print(f"✅ ChromaDB loaded: {collection.count():,} documents")

    # Initialize hybrid search engine
    hybrid_engine = HybridSearchEngine(collection)

    # Warm up the LLM model
    print("🔥 Warming up LLM model...")
    warm_up_success = warm_up_model(model="llama3.2:3b", timeout=60)

    if warm_up_success:
        print("✅ API server ready!")
    else:
        print("⚠️  API server started, but LLM warm-up failed. Check Ollama service.")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print("🛑 Shutting down API server...")


# API Endpoints

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "RAG Documentation Assistant API",
        "version": "1.0.0",
        "endpoints": {
            "query": "POST /query - Question answering with LLM",
            "search": "POST /search - Document search only",
            "domains": "GET /domains - List available domains",
            "health": "GET /health - System health check",
            "docs": "GET /docs - API documentation (Swagger UI)"
        }
    }


@app.post("/query", response_model=QueryResponse, tags=["Question Answering"])
@limiter.limit("10/minute")
async def query_documents(request: Request, query_request: QueryRequest):
    """
    Full RAG pipeline: retrieve relevant documents and generate answer with LLM.

    Supports streaming responses for real-time answer generation.
    """
    try:
        # Build filter metadata
        filter_metadata = {"domain": query_request.domain} if query_request.domain else None

        # For streaming, return StreamingResponse
        if query_request.stream:
            async def generate_streaming_response():
                """Generator for streaming LLM response."""
                start_time = time.time()

                # Step 1: Retrieve chunks
                from src.vector_store import query_similar_chunks
                from src.reranker import rerank_chunks

                search_start = time.time()
                initial_n = query_request.n_results * 3 if query_request.use_reranking else query_request.n_results

                if query_request.search_method in ["hybrid", "bm25"]:
                    results = hybrid_engine.search(
                        query=query_request.question,
                        n_results=initial_n,
                        domain=query_request.domain,
                        method=query_request.search_method
                    )
                    chunks = [r['document'] for r in results]
                    metadatas = [r['metadata'] for r in results]
                else:
                    results = query_similar_chunks(collection, query_request.question, n_results=initial_n, filter_metadata=filter_metadata)
                    chunks = results['documents'][0]
                    metadatas = results['metadatas'][0]

                search_time = time.time() - search_start

                # Rerank if enabled
                if query_request.use_reranking and len(chunks) > query_request.n_results:
                    chunks, metadatas = rerank_chunks(
                        query=query_request.question,
                        chunks=chunks,
                        metadatas=metadatas,
                        top_k=query_request.n_results,
                        method="ollama"
                    )

                # Send metadata first
                yield json.dumps({
                    "type": "metadata",
                    "search_time": search_time,
                    "chunks_retrieved": len(chunks)
                }) + "\n"

                # Step 2: Stream LLM response
                import requests

                # Build prompt
                context_parts = []
                for i, chunk in enumerate(chunks[:3], 1):
                    preview = chunk[:300] if len(chunk) > 300 else chunk
                    context_parts.append(f"[Document {i}]\n{preview}")

                context = "\n\n".join(context_parts)
                prompt = f"""You are a helpful assistant. Answer based ONLY on the context below.

Context:
{context}

Question: {query_request.question}

Instructions:
- Be concise (2-3 sentences max)
- Cite document numbers
- If not in context, say "I don't have enough information"

Answer:"""

                # Stream from Ollama
                response = requests.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": "llama3.2:3b",
                        "prompt": prompt,
                        "stream": True,
                        "options": {
                            "num_predict": 150,
                            "temperature": 0.7,
                            "top_p": 0.9
                        }
                    },
                    stream=True,
                    timeout=30
                )

                full_answer = ""
                for line in response.iter_lines(decode_unicode=True):
                    if line:
                        try:
                            data = json.loads(line)
                            if 'response' in data:
                                token = data['response']
                                full_answer += token
                                # Send token
                                yield json.dumps({
                                    "type": "token",
                                    "token": token
                                }) + "\n"

                            if data.get('done', False):
                                break
                        except:
                            continue

                # Send final response with sources
                sources = []
                for i, metadata in enumerate(metadatas):
                    source_info = {
                        "source": metadata.get('source', 'Unknown'),
                        "source_type": metadata.get('source_type', 'pdf'),
                        "chunk_preview": chunks[i][:200] + "..."
                    }
                    if metadata.get('source_type') == 'csv':
                        source_info['row_id'] = metadata.get('row_id', 'N/A')
                        source_info['brand'] = metadata.get('brand', 'N/A')
                        source_info['category'] = metadata.get('category', 'N/A')
                    else:
                        source_info['page'] = metadata.get('page', 'N/A')
                    sources.append(source_info)

                total_time = time.time() - start_time
                yield json.dumps({
                    "type": "done",
                    "answer": full_answer.strip(),
                    "sources": sources,
                    "total_time": total_time
                }) + "\n"

            return StreamingResponse(
                generate_streaming_response(),
                media_type="application/x-ndjson"
            )

        else:
            # Non-streaming mode
            result = ask_question(
                collection=collection,
                question=query_request.question,
                n_results=query_request.n_results,
                filter_metadata=filter_metadata,
                search_method=query_request.search_method,
                use_reranking=query_request.use_reranking,
                use_cache=query_request.use_cache,
                stream=False
            )

            return QueryResponse(
                question=result["question"],
                answer=result["answer"],
                sources=result["sources"],
                metadata={
                    "search_method": query_request.search_method,
                    "reranking_used": query_request.use_reranking,
                    "chunks_retrieved": len(result["retrieved_chunks"])
                }
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search", response_model=SearchResponse, tags=["Search"])
@limiter.limit("20/minute")
async def search_documents(request: Request, search_request: SearchRequest):
    """
    Search for relevant documents without LLM generation.

    Returns raw search results with metadata.
    """
    try:
        if search_request.search_method in ["hybrid", "bm25"]:
            results = hybrid_engine.search(
                query=search_request.query,
                n_results=search_request.n_results,
                domain=search_request.domain,
                method=search_request.search_method
            )
        else:
            # Semantic search
            filter_metadata = {"domain": search_request.domain} if search_request.domain else None
            from src.vector_store import query_similar_chunks
            chroma_results = query_similar_chunks(
                collection,
                search_request.query,
                n_results=search_request.n_results,
                filter_metadata=filter_metadata
            )

            results = [
                {
                    "document": chroma_results['documents'][0][i],
                    "distance": chroma_results['distances'][0][i],
                    "metadata": chroma_results['metadatas'][0][i]
                }
                for i in range(len(chroma_results['documents'][0]))
            ]

        return SearchResponse(
            query=search_request.query,
            results=results,
            metadata={
                "search_method": search_request.search_method,
                "domain": search_request.domain,
                "total_results": len(results)
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/domains", response_model=DomainResponse, tags=["Domains"])
async def get_domains():
    """
    Get list of available domains with document counts.
    """
    try:
        # Get all metadatas
        all_data = collection.get(include=["metadatas"])
        metadatas = all_data['metadatas']

        # Count by domain
        domain_counts = {}
        for metadata in metadatas:
            domain = metadata.get('domain', 'unknown')
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        domains = [
            {
                "name": domain,
                "document_count": count,
                "description": f"{domain.capitalize()} documentation"
            }
            for domain, count in domain_counts.items()
        ]

        return DomainResponse(domains=domains)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    System health check endpoint.

    Returns status of all components and performance metrics.
    """
    try:
        # Check Ollama
        import requests
        ollama_running = False
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=2)
            ollama_running = resp.status_code == 200
        except:
            pass

        # Check database
        database_ready = collection is not None and collection.count() > 0

        # Get cache and performance stats
        cache = get_query_cache()
        monitor = get_performance_monitor()

        return HealthResponse(
            status="healthy" if (ollama_running and database_ready) else "degraded",
            ollama_running=ollama_running,
            database_ready=database_ready,
            documents_indexed=collection.count() if collection else 0,
            cache_size=len(cache.cache),
            performance_stats=monitor.get_stats()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feedback", tags=["Feedback"])
@limiter.limit("30/minute")
async def submit_feedback(request: Request, feedback_request: FeedbackRequest):
    """
    Submit user feedback for an answer.

    Allows users to rate answers with thumbs up/down and optional comments.
    This data is used to track answer quality and improve the system.
    """
    try:
        feedback_mgr = get_feedback_manager()

        # Save feedback
        feedback_entry = feedback_mgr.save_feedback(
            question=feedback_request.question,
            answer=feedback_request.answer,
            rating=feedback_request.rating,
            comment=feedback_request.comment,
            domain=feedback_request.domain,
            metadata=feedback_request.metadata or {}
        )

        return {
            "status": "success",
            "message": "Feedback submitted successfully",
            "feedback_id": feedback_entry["id"]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/feedback/stats", tags=["Feedback"])
async def get_feedback_stats():
    """
    Get feedback statistics and analytics.

    Returns overall satisfaction rate, domain breakdown, and recent feedback.
    """
    try:
        feedback_mgr = get_feedback_manager()
        stats = feedback_mgr.get_statistics()
        recent = feedback_mgr.get_recent_feedback(limit=10)

        return {
            "status": "success",
            "statistics": stats,
            "recent_feedback": recent
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/feedback/export", tags=["Feedback"])
async def export_feedback(
    format: str = "csv",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Export feedback data in CSV or JSON format.

    Args:
        format: Export format ('csv' or 'json')
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)

    Returns:
        Downloadable file with feedback data
    """
    try:
        feedback_mgr = get_feedback_manager()

        if format.lower() == "csv":
            content = feedback_mgr.export_to_csv(start_date=start_date, end_date=end_date)
            media_type = "text/csv"
            filename = f"feedback_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        elif format.lower() == "json":
            content = feedback_mgr.export_to_json(start_date=start_date, end_date=end_date)
            media_type = "application/json"
            filename = f"feedback_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        else:
            raise HTTPException(status_code=400, detail="Invalid format. Use 'csv' or 'json'")

        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload", tags=["Upload"])
@limiter.limit("5/minute")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    domain: str = Form(...)
):
    """
    Upload a document (PDF or CSV) and index it.

    Args:
        file: The file to upload (PDF or CSV)
        domain: The domain to add the document to

    Returns:
        Success message with indexing details
    """
    global collection, hybrid_engine

    try:
        # Validate file type
        allowed_extensions = ['.pdf', '.csv']
        file_ext = Path(file.filename).suffix.lower()

        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
            )

        # Create domain directory if it doesn't exist
        data_dir = Path(__file__).parent.parent / "data" / domain
        data_dir.mkdir(parents=True, exist_ok=True)

        # Save file
        file_path = data_dir / file.filename

        # Check if file already exists
        if file_path.exists():
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' already exists in domain '{domain}'"
            )

        # Write file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Index the file directly (incremental, doesn't clear existing data)
        from src.pdf_loader import load_pdfs_from_directory
        from src.csv_loader import load_csv_as_documents
        from src.vector_store import index_documents

        documents = []

        # Load document based on type
        if file_ext == '.pdf':
            # Load PDF
            docs = load_pdfs_from_directory(str(data_dir), domain=domain)
            # Filter to only the newly uploaded file
            documents = [doc for doc in docs if file.filename in doc.metadata.get('source', '')]
        elif file_ext == '.csv':
            # Load CSV
            documents = load_csv_as_documents(str(file_path), domain=domain)

        if not documents:
            file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=500,
                detail=f"No documents loaded from file. File might be empty or invalid."
            )

        # Add to existing collection (incremental)
        index_documents(collection, documents)

        # Reload collection to get updated count
        collection = chroma_client.get_collection(name="documents")

        # Rebuild hybrid engine to include new documents
        from src.hybrid_search import HybridSearchEngine
        hybrid_engine = HybridSearchEngine(collection)

        return {
            "status": "success",
            "message": f"File '{file.filename}' uploaded and indexed successfully",
            "domain": domain,
            "file_path": str(file_path),
            "total_documents": collection.count()
        }

    except HTTPException:
        raise

    except Exception as e:
        # Clean up file if any error
        if 'file_path' in locals() and file_path.exists():
            file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/domain/{domain_name}", tags=["Delete"])
async def delete_domain(domain_name: str):
    """
    Delete an entire domain and all its documents.

    Args:
        domain_name: The name of the domain to delete

    Returns:
        Success message with deletion details
    """
    global collection, hybrid_engine

    try:
        # Get all documents from this domain to count them
        results = collection.get(
            where={"domain": domain_name},
            include=["metadatas"]
        )

        doc_count = len(results['ids'])

        if doc_count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Domain '{domain_name}' not found or has no documents"
            )

        # Delete all documents from this domain in ChromaDB
        collection.delete(where={"domain": domain_name})

        # Delete domain folder from filesystem
        domain_dir = Path(__file__).parent.parent / "data" / domain_name
        if domain_dir.exists():
            shutil.rmtree(domain_dir)
            folder_deleted = True
        else:
            folder_deleted = False

        # Reload collection to get updated count
        collection = chroma_client.get_collection(name="documents")

        # Rebuild hybrid engine
        from src.hybrid_search import HybridSearchEngine
        hybrid_engine = HybridSearchEngine(collection)

        return {
            "status": "success",
            "message": f"Domain '{domain_name}' deleted successfully",
            "documents_deleted": doc_count,
            "folder_deleted": folder_deleted,
            "total_documents_remaining": collection.count()
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
