"""
Admin Pricing API Routes

Endpoints para gerenciar tabela de preços de LLMs.
Acesso restrito a master admins.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import require_master_admin
from app.core.database import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/pricing", tags=["Admin Pricing"])



# ============================================================================
# MODELS
# ============================================================================

class PricingItem(BaseModel):
    id: str
    model_name: str
    input_price_per_million: float
    output_price_per_million: float
    unit: str
    is_active: bool
    provider: Optional[str]
    display_name: Optional[str]
    sell_multiplier: Optional[float] = 2.68


class PricingUpdateRequest(BaseModel):
    input_price_per_million: Optional[float] = None
    output_price_per_million: Optional[float] = None
    is_active: Optional[bool] = None
    display_name: Optional[str] = None
    sell_multiplier: Optional[float] = None


class PricingListResponse(BaseModel):
    success: bool
    data: List[PricingItem]
    count: int


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("", response_model=PricingListResponse)
async def list_pricing(
    _: bool = Depends(require_master_admin)
):
    """
    Lista todos os modelos de pricing.
    Retorna agrupado por provider.
    """
    try:
        supabase = get_supabase_client()

        result = supabase.client.table("llm_pricing") \
            .select("*") \
            .order("provider") \
            .order("model_name") \
            .execute()

        return {
            "success": True,
            "data": result.data or [],
            "count": len(result.data) if result.data else 0
        }

    except Exception as e:
        logger.error(f"[Pricing API] Error listing pricing: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/{pricing_id}")
async def update_pricing(
    pricing_id: str,
    request: PricingUpdateRequest,
    _: bool = Depends(require_master_admin)
):
    """
    Atualiza preço de um modelo específico.
    """
    try:
        supabase = get_supabase_client()

        # Build update payload
        update_data = {}
        if request.input_price_per_million is not None:
            update_data["input_price_per_million"] = request.input_price_per_million
        if request.output_price_per_million is not None:
            update_data["output_price_per_million"] = request.output_price_per_million
        if request.is_active is not None:
            update_data["is_active"] = request.is_active
        if request.display_name is not None:
            update_data["display_name"] = request.display_name
        if request.sell_multiplier is not None:
            update_data["sell_multiplier"] = request.sell_multiplier

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Add updated_at
        from datetime import datetime
        update_data["updated_at"] = datetime.utcnow().isoformat()

        result = supabase.client.table("llm_pricing") \
            .update(update_data) \
            .eq("id", pricing_id) \
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Pricing not found")

        logger.info(f"[Pricing API] Updated pricing {pricing_id}")

        return {
            "success": True,
            "data": result.data[0]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Pricing API] Error updating pricing: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/reload-cache")
async def reload_cache(
    _: bool = Depends(require_master_admin)
):
    """
    Força reload do cache de pricing em memória.
    Chame após atualizar preços no banco.
    """
    try:
        from app.services.usage_service import get_usage_service

        service = get_usage_service()
        count = service.reload_cache()

        logger.info(f"[Pricing API] Cache reloaded: {count} models")

        return {
            "success": True,
            "message": f"Cache reloaded with {count} models",
            "count": count
        }

    except Exception as e:
        logger.error(f"[Pricing API] Error reloading cache: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
