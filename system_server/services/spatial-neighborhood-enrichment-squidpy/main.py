import os
import uuid
import tempfile
import traceback
from typing import Dict, Any, Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
import uvicorn

from algorithm import process_neighborhood_enrichment

app = FastAPI(
    title="Spatial Neighborhood Enrichment (Squidpy)",
    description="Calculate neighborhood enrichment between cluster categories using Squidpy.",
    version="1.0.0",
)

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def format_error_info_to_message(error_info: Dict[str, Any]) -> str:
    """Format error_info dictionary into a readable string message"""
    parts = []
    parts.append(f"Error Type: {error_info.get('error_type', 'Unknown')}")
    parts.append(f"Error Message: {error_info.get('error_message', 'Unknown error')}")
    if "diagnosis" in error_info:
        parts.append(f"\nDiagnosis: {error_info['diagnosis']}")
    if "suggestions" in error_info and error_info["suggestions"]:
        parts.append("\nSuggestions:")
        for idx, suggestion in enumerate(error_info["suggestions"], 1):
            if isinstance(suggestion, dict):
                issue = suggestion.get("issue", "Unknown issue")
                recommendations = suggestion.get("recommendations", [])
                parts.append(f"\n  {idx}. {issue}:")
                for rec in recommendations:
                    parts.append(f"     - {rec}")
    return "\n".join(parts)


def handle_error(step: str, error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Unified error handling function that provides detailed error messages and parameter suggestions"""
    error_info = {
        "error": True,
        "step": step,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "suggestions": []
    }
    error_msg_lower = str(error).lower()
    
    if "file" in error_msg_lower or "read" in error_msg_lower:
        error_info["diagnosis"] = "File reading or format issue"
        error_info["suggestions"].extend([{
            "issue": "File format mismatch or file corrupted",
            "recommendations": [
                "Check if file format is correct (must be h5ad)",
                "Ensure the spatial_key and cluster_key exist in your dataset"
            ]
        }])
    elif "key" in error_msg_lower:
        error_info["diagnosis"] = "Missing metadata key in AnnData"
        error_info["suggestions"].extend([{
            "issue": "The specified Spatial/Cluster Key could not be found",
            "recommendations": [
                "Verify that the 'cluster_key' exists in adata.obs (e.g. 'leiden' or 'cell_type')",
                "Verify that the 'spatial_key' exists in adata.obsm (e.g. 'spatial')"
            ]
        }])
    elif "memory" in error_msg_lower:
        error_info["diagnosis"] = "Out of memory"
        error_info["suggestions"].extend([{
            "issue": "Dataset is too large or permutation count is too high",
            "recommendations": [
                "Reduce the number of permutations ('n_perms')",
                "Subsample your dataset before running"
            ]
        }])
    else:
        error_info["diagnosis"] = "Algorithm execution failed"
        error_info["suggestions"].extend([{
            "issue": "Unknown runtime error during spatial neighborhood enrichment",
            "recommendations": [
                "Check your input h5ad attributes to ensure they match squidpy expectations",
                "Ensure clustering labels are discrete/categorical"
            ]
        }])
        
    return error_info


@app.post("/api/neighborhood-enrichment")
async def neighborhood_enrichment(
    file: UploadFile = File(...),
    file_type: str = Form("auto"),
    spatial_key: str = Form("spatial"),
    cluster_key: str = Form("leiden"),
    n_neighbors: int = Form(6),
    radius: Optional[float] = Form(None),
    n_perms: int = Form(1000),
    seed: int = Form(0)
) -> JSONResponse:
    """Execute spatial neighborhood enrichment API"""
    temp_input_path = None
    try:
        # Save uploaded file
        file_id = str(uuid.uuid4())
        temp_input_path = os.path.join(tempfile.gettempdir(), f"input_{file_id}_{file.filename}")
        
        with open(temp_input_path, "wb") as f:
            content = await file.read()
            f.write(content)
            
        # Create a unique output directory prefix to prevent collisions
        request_id = str(uuid.uuid4())
        
        context = {
            "spatial_key": spatial_key, 
            "cluster_key": cluster_key, 
            "n_neighbors": n_neighbors,
            "radius": radius
        }
        
        # Execute algorithm logic
        output_files = process_neighborhood_enrichment(
            adata_path=temp_input_path,
            cluster_key=cluster_key,
            n_neighbors=n_neighbors,
            radius=radius,
            n_perms=n_perms,
            seed=seed,
            output_dir=OUTPUT_DIR
        )
        
        # Rename outputs securely using request ID to ensure uniqueness in OUTPUT_DIR
        data_dict = {}
        for logical_name, temp_name in output_files.items():
            ext = os.path.splitext(logical_name)[1]
            unique_filename = f"{request_id}_{logical_name}"
            
            # Since algorithm currently wrote it globally in OUTPUT_DIR as temp_name
            # Rename it to the unique id
            old_path = os.path.join(OUTPUT_DIR, temp_name)
            new_path = os.path.join(OUTPUT_DIR, unique_filename)
            if os.path.exists(old_path):
                os.rename(old_path, new_path)
            
            data_dict[logical_name] = unique_filename
            
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Neighborhood enrichment analysis completed successfully.", "data": data_dict},
        )
        
    except Exception as e:
        traceback.print_exc()
        context = {"cluster_key": cluster_key}
        error_info = handle_error("execution_step", e, context=context)
        error_message = format_error_info_to_message(error_info)
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": error_message
            }
        )
    finally:
        if temp_input_path and os.path.exists(temp_input_path):
            try:
                os.remove(temp_input_path)
            except:
                pass

@app.get("/api/download/{file_id}")
async def download_file(file_id: str) -> FileResponse:
    """Download result file"""
    file_path = os.path.join(OUTPUT_DIR, file_id)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file_id}")
        
    if file_path.endswith(".png"):
        media_type = "image/png"
    elif file_path.endswith(".h5ad"):
        media_type = "application/octet-stream"
    elif file_path.endswith(".csv"):
        media_type = "text/csv"
    else:
        media_type = "text/plain"
        
    # We download it nicely restoring original name if we can, 
    # but the platform handles filenames, so ID serves fine.
    return FileResponse(path=file_path, filename=file_id, media_type=media_type)

@app.get("/health")
async def health():
    return {"status": "healthy", "output_dir": OUTPUT_DIR}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 53901))
    uvicorn.run(app, host="0.0.0.0", port=port)
