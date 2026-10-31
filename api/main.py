"""
FastAPI Backend for Multi-Domain RAG

This API provides RESTful endpoints for:
- Question answering with LLM (streaming)
- Document search and retrieval
- Domain management
- System health monitoring

Usage:
    uvicorn api.main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import json
import chromadb
from pathlib import Path
from datetime import datetime
import time
import shutil
import subprocess

from rag import config
from rag.retrieval.vector_store import get_chroma_client
from rag.qa_chain import (ask_question, warm_up_model, generate_answer_ollama,
                          build_prompt, format_sources, mark_cited, public_metadata,
                          LLM_ERROR_PREFIX, NO_ANSWER)
from rag.retrieval.hybrid_search import HybridSearchEngine
from rag.caching.cache_manager import get_query_cache, get_performance_monitor
from rag.feedback_manager import get_feedback_manager
from rag.caching.semantic_cache import get_semantic_cache
from rag.retrieval.embeddings import create_embedding
from rag.auth import get_user_manager, create_access_token, verify_token

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize FastAPI app
app = FastAPI(
    title="Multi-Domain RAG API",
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

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# Authentication dependency
async def get_current_user(token: str = Depends(oauth2_scheme)) -> Optional[Dict[str, Any]]:
    """
    Get current authenticated user from JWT token.

    Returns None if no token or invalid token (allows optional authentication).
    """
    if not token:
        return None

    username = verify_token(token)
    if not username:
        return None

    user_manager = get_user_manager()
    user = user_manager.get_user(username)
    return user


async def require_auth(current_user: Optional[Dict[str, Any]] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Require authentication (raises 401 if not authenticated).
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


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


class RegisterRequest(BaseModel):
    username: str = Field(..., description="Unique username", min_length=3, max_length=50)
    password: str = Field(..., description="Password", min_length=6)
    email: Optional[str] = Field(None, description="Email address")
    full_name: Optional[str] = Field(None, description="Full name")


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: Dict[str, Any]


class UserResponse(BaseModel):
    username: str
    email: Optional[str]
    full_name: Optional[str]
    created_at: str
    is_active: bool


# Startup/Shutdown Events
@app.on_event("startup")
async def startup_event():
    """Initialize ChromaDB and warm up the model."""
    global chroma_client, collection, hybrid_engine

    print("Starting RAG API server...")

    # Initialize ChromaDB
    config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    chroma_client = get_chroma_client(config.CHROMA_DIR)
    collection = chroma_client.get_or_create_collection(name=config.COLLECTION_NAME)

    print(f"ChromaDB loaded: {collection.count():,} documents")

    # Initialize hybrid search engine
    hybrid_engine = HybridSearchEngine(collection)

    # Warm up the LLM model
    print("Warming up LLM model...")
    warm_up_success = warm_up_model(model=config.LLM_MODEL, timeout=60)

    if warm_up_success:
        print("API server ready!")
    else:
        print("API server started, but LLM warm-up failed. Check Ollama service.")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print("Shutting down API server...")


def retrieval_settings(request: "QueryRequest") -> Dict[str, Any]:
    """Settings that change which chunks reach the LLM. Cached answers are only reused with equal settings."""
    return {
        "search_method": request.search_method,
        "n_results": request.n_results,
        "use_reranking": request.use_reranking,
    }


def store_in_semantic_cache(request: "QueryRequest", embedding, answer: str, sources: list):
    """Cache a finished answer. Empty answers and LLM errors are not cached."""
    if not request.use_cache or embedding is None:
        return
    if not answer or answer.startswith(LLM_ERROR_PREFIX):
        return
    get_semantic_cache().set(
        query=request.question,
        query_embedding=embedding,
        answer=answer,
        sources=sources,
        domain=request.domain,
        metadata={
            "search_method": request.search_method,
            "reranking_used": request.use_reranking
        },
        settings=retrieval_settings(request)
    )


def stream_cached_answer(cached: Dict[str, Any]):
    """Replay a cached answer in the same NDJSON format as a live streamed answer."""
    meta = cached.get("metadata", {})
    info = {
        "cache_hit": True,
        "cache_similarity": meta.get("cache_similarity"),
        "cached_query": meta.get("cached_query"),
    }
    yield json.dumps({"type": "metadata", "search_time": 0.0,
                      "chunks_retrieved": len(cached["sources"]), **info}) + "\n"
    yield json.dumps({"type": "token", "token": cached["answer"]}) + "\n"
    yield json.dumps({"type": "done", "answer": cached["answer"],
                      "sources": cached["sources"], "total_time": 0.0, **info}) + "\n"


def ensure_current_collection():
    """
    Pick up changes made outside this process.

    scripts.index_documents drops and recreates the collection. The old handle
    then raises an error, and the keyword index no longer matches. Compare the
    live collection (id and size) with the one the engine was built from and
    rebuild when they differ.
    """
    global collection
    if chroma_client is None:
        return
    current = chroma_client.get_or_create_collection(name=config.COLLECTION_NAME)
    if (collection is None or hybrid_engine is None
            or current.id != collection.id or current.count() != hybrid_engine.size):
        collection = current
        refresh_search_state()


def refresh_search_state():
    """Rebuild the keyword index and drop cached answers after the documents changed."""
    global hybrid_engine
    hybrid_engine = HybridSearchEngine(collection)
    get_semantic_cache().clear()
    get_query_cache().clear()


# API Endpoints

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Multi-Domain RAG API",
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
        ensure_current_collection()
        # Build filter metadata
        filter_metadata = {"domain": query_request.domain} if query_request.domain else None

        # Check semantic cache (if enabled)
        query_embedding = None
        if query_request.use_cache:
            semantic_cache = get_semantic_cache()
            query_embedding = create_embedding(query_request.question)

            cached_result = semantic_cache.get(
                query=query_request.question,
                query_embedding=query_embedding,
                domain=query_request.domain,
                settings=retrieval_settings(query_request)
            )

            if cached_result:
                if query_request.stream:
                    return StreamingResponse(
                        stream_cached_answer(cached_result),
                        media_type="application/x-ndjson"
                    )
                return QueryResponse(
                    question=query_request.question,
                    answer=cached_result['answer'],
                    sources=cached_result['sources'],
                    metadata=cached_result['metadata']
                )

        # For streaming, return StreamingResponse
        if query_request.stream:
            async def generate_streaming_response():
                """Generator for streaming LLM response."""
                start_time = time.time()

                # Step 1: Retrieve chunks
                from rag.retrieval.vector_store import query_similar_chunks
                from rag.retrieval.reranker import rerank_chunks

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

                sources = format_sources(chunks, metadatas)

                # Nothing retrieved: do not ask the LLM to answer from an empty context
                if not chunks:
                    yield json.dumps({"type": "token", "token": NO_ANSWER}) + "\n"
                    yield json.dumps({
                        "type": "done",
                        "answer": NO_ANSWER,
                        "sources": [],
                        "total_time": time.time() - start_time
                    }) + "\n"
                    return

                # Step 2: Stream LLM response
                import requests

                prompt = build_prompt(query_request.question, chunks)
                full_answer = ""
                failed = False

                try:
                    response = requests.post(
                        f"{config.OLLAMA_URL}/api/generate",
                        json={
                            "model": config.LLM_MODEL,
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
                    if response.status_code != 200:
                        raise RuntimeError(f"Ollama returned HTTP {response.status_code}")

                    for line in response.iter_lines(decode_unicode=True):
                        if line:
                            try:
                                data = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            if 'response' in data:
                                token = data['response']
                                full_answer += token
                                yield json.dumps({"type": "token", "token": token}) + "\n"
                            if data.get('done', False):
                                break
                except Exception as e:
                    # Ollama unreachable or failed part way: report it in the stream
                    failed = True
                    message = f"{LLM_ERROR_PREFIX}{e}"
                    full_answer = (full_answer + "\n" + message).strip()
                    yield json.dumps({"type": "token", "token": message}) + "\n"

                full_answer = full_answer.strip()
                mark_cited(full_answer, sources)
                if not failed:
                    store_in_semantic_cache(query_request, query_embedding, full_answer, sources)

                total_time = time.time() - start_time
                yield json.dumps({
                    "type": "done",
                    "answer": full_answer,
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
                stream=False,
                engine=hybrid_engine
            )

            # Store in semantic cache (if enabled and not already cached)
            store_in_semantic_cache(query_request, query_embedding, result["answer"], result["sources"])

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

    Returns search results with metadata. File names are shown without directories and PDF pages start at 1.
    """
    try:
        ensure_current_collection()
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
            from rag.retrieval.vector_store import query_similar_chunks
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

        results = [{**r, "metadata": public_metadata(r["metadata"])} for r in results]

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
        ensure_current_collection()
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
            resp = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=2)
            ollama_running = resp.status_code == 200
        except:
            pass

        # Check database and guard against collection recreation
        global chroma_client, collection, hybrid_engine
        documents_indexed = 0
        database_ready = False
        try:
            if collection is not None:
                documents_indexed = collection.count()
                database_ready = documents_indexed > 0
        except Exception:
            # The underlying collection may have been recreated externally (e.g., reindexing)
            # Refresh the collection reference and rebuild dependent engines
            collection = chroma_client.get_or_create_collection(name=config.COLLECTION_NAME)
            documents_indexed = collection.count()
            database_ready = documents_indexed > 0
            try:
                from rag.retrieval.hybrid_search import HybridSearchEngine
                hybrid_engine = HybridSearchEngine(collection)
            except Exception:
                # If hybrid engine rebuild fails, continue with health response
                pass

        # Get cache and performance stats
        cache = get_query_cache()
        monitor = get_performance_monitor()
        semantic_cache = get_semantic_cache()

        # Combine performance stats with semantic cache stats
        perf_stats = monitor.get_stats()
        perf_stats['semantic_cache'] = semantic_cache.get_stats()

        return HealthResponse(
            status="healthy" if (ollama_running and database_ready) else "degraded",
            ollama_running=ollama_running,
            database_ready=database_ready,
            documents_indexed=documents_indexed,
            cache_size=len(cache.cache),
            performance_stats=perf_stats
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
    domain: str = Form(...),
    current_user: Dict[str, Any] = Depends(require_auth)
):
    """
    Upload a document (PDF or CSV) and index it.

    Requires: Authentication

    Args:
        file: The file to upload (PDF or CSV)
        domain: The domain to add the document to

    Returns:
        Success message with indexing details
    """
    global collection, hybrid_engine

    try:
        ensure_current_collection()
        # Validate file type
        allowed_extensions = ['.pdf', '.csv']
        file_ext = Path(file.filename).suffix.lower()

        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
            )

        # Create domain directory if it doesn't exist
        data_dir = config.DATA_DIR / domain
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
        from rag.ingestion.pdf_loader import load_pdfs_from_directory
        from rag.ingestion.csv_loader import load_csv_as_documents
        from rag.retrieval.vector_store import index_documents

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
        collection = chroma_client.get_collection(name=config.COLLECTION_NAME)

        refresh_search_state()

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
async def delete_domain(
    domain_name: str,
    current_user: Dict[str, Any] = Depends(require_auth)
):
    """
    Delete an entire domain and all its documents.

    Requires: Authentication

    Args:
        domain_name: The name of the domain to delete

    Returns:
        Success message with deletion details
    """
    global collection, hybrid_engine

    try:
        ensure_current_collection()
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
        domain_dir = config.DATA_DIR / domain_name
        if domain_dir.exists():
            shutil.rmtree(domain_dir)
            folder_deleted = True
        else:
            folder_deleted = False

        # Reload collection to get updated count
        collection = chroma_client.get_collection(name=config.COLLECTION_NAME)

        refresh_search_state()

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


# Authentication Endpoints

@app.post("/auth/register", response_model=UserResponse, tags=["Authentication"])
async def register(register_data: RegisterRequest):
    """
    Register a new user account.

    Args:
        register_data: User registration data (username, password, email, full_name)

    Returns:
        Created user information (without password)

    Raises:
        400: If username already exists
    """
    try:
        user_manager = get_user_manager()

        user = user_manager.create_user(
            username=register_data.username,
            password=register_data.password,
            email=register_data.email,
            full_name=register_data.full_name
        )

        return UserResponse(**user)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/auth/login", response_model=LoginResponse, tags=["Authentication"])
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login with username and password.

    Args:
        form_data: OAuth2 form with username and password

    Returns:
        JWT access token and user information

    Raises:
        401: If credentials are invalid
    """
    try:
        user_manager = get_user_manager()

        # Authenticate user
        user = user_manager.authenticate_user(
            username=form_data.username,
            password=form_data.password
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Create access token
        from datetime import timedelta
        access_token = create_access_token(
            data={"sub": user['username']},
            expires_delta=timedelta(minutes=1440)  # 24 hours
        )

        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            user=user
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/me", response_model=UserResponse, tags=["Authentication"])
async def get_current_user_info(current_user: Dict[str, Any] = Depends(require_auth)):
    """
    Get current authenticated user information.

    Requires: Valid JWT token

    Returns:
        Current user information
    """
    return UserResponse(**current_user)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
