"""
Esquemas Pydantic para validación de datos e interfaces de herramientas LLM
Estos modelos sirven tanto para la validación de la base de datos como para los esquemas de salida estructurada de LLM
"""

from typing import Dict, Literal, Optional, List
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from datetime import date, datetime


# Define valores permitidos como Literals para compatibilidad con LLM
RegionType = Literal[
    "north_america",
    "europe",
    "asia",
    "latin_america",
    "africa",
    "middle_east",
    "oceania",
    "global",
    "international",  # Para mezclas no estadounidenses
]

AssetClassType = Literal[
    "equity", "fixed_income", "real_estate", "commodities", "cash", "alternatives"
]

SectorType = Literal[
    "technology",
    "healthcare",
    "financials",
    "consumer_discretionary",
    "consumer_staples",
    "industrials",
    "energy",
    "materials",
    "utilities",
    "real_estate",
    "communication",
    "treasury",
    "corporate",
    "mortgage",
    "government_related",
    "commodities",
    "diversified",
    "other",
]

InstrumentType = Literal["etf", "mutual_fund", "stock", "bond", "bond_fund", "commodity", "reit"]

JobType = Literal[
    "portfolio_analysis",
    "rebalance_recommendation",
    "retirement_projection",
    "risk_assessment",
    "tax_optimization",
    "instrument_research",
]

JobStatus = Literal["pending", "running", "completed", "failed"]

AccountType = Literal[
    "401k", "roth_ira", "traditional_ira", "taxable", "529", "hsa", "pension", "other"
]


class AllocationDict(BaseModel):
    """Clase base para diccionarios de asignación asegurando que sumen 100"""

    @field_validator("*", mode="after")
    def validate_sum(cls, v, info):
        """Asegurar que los porcentajes de asignación sumen 100"""
        if isinstance(v, dict):
            total = sum(v.values())
            if abs(total - 100) > 3:  # Permitir pequeños errores de punto flotante
                raise ValueError(f"Las asignaciones deben sumar 100, se obtuvo {total}")
        return v


class RegionAllocation(BaseModel):
    """Asignación geográfica de un instrumento"""

    allocations: Dict[RegionType, float] = Field(
        description="Porcentaje de asignación por región geográfica. Debe sumar 100.",
        example={"north_america": 60, "europe": 25, "asia": 15},
    )

    @field_validator("allocations")
    def validate_sum(cls, v):
        total = sum(v.values())
        if abs(total - 100) > 3:
            raise ValueError(f"Las asignaciones regionales deben sumar 100, se obtuvo {total}")
        return v


class AssetClassAllocation(BaseModel):
    """Asignación por clase de activo de un instrumento"""

    allocations: Dict[AssetClassType, float] = Field(
        description="Porcentaje de asignación por clase de activo. Debe sumar 100.",
        example={"equity": 80, "fixed_income": 20},
    )

    @field_validator("allocations")
    def validate_sum(cls, v):
        total = sum(v.values())
        if abs(total - 100) > 3:
            raise ValueError(f"Las asignaciones de clase de activo deben sumar 100, se obtuvo {total}")
        return v


class SectorAllocation(BaseModel):
    """Asignación sectorial de un instrumento"""

    allocations: Dict[SectorType, float] = Field(
        description="Porcentaje de asignación por sector de mercado. Debe sumar 100.",
        example={"technology": 30, "healthcare": 25, "financials": 20, "other": 25},
    )

    @field_validator("allocations")
    def validate_sum(cls, v):
        total = sum(v.values())
        if abs(total - 100) > 3:
            raise ValueError(f"Las asignaciones sectoriales deben sumar 100, se obtuvo {total}")
        return v


class InstrumentCreate(BaseModel):
    """Esquema para crear un nuevo instrumento - adecuado para entrada de herramienta LLM"""

    symbol: str = Field(
        description="El símbolo bursátil del instrumento (p. ej., 'SPY', 'BND')",
        min_length=1,
        max_length=20,
    )
    name: str = Field(description="Nombre completo del instrumento", min_length=1, max_length=255)
    instrument_type: InstrumentType = Field(description="El tipo de instrumento financiero")
    current_price: Optional[Decimal] = Field(
        None,
        description="Precio actual del instrumento para cálculos de portafolio",
        ge=0,
        le=999999,
    )
    allocation_regions: Dict[RegionType, float] = Field(
        description="Porcentajes de asignación geográfica. Deben sumar 100.",
        example={"north_america": 100},
    )
    allocation_sectors: Dict[SectorType, float] = Field(
        description="Porcentajes de asignación sectorial. Deben sumar 100.",
        example={"technology": 40, "healthcare": 30, "financials": 30},
    )
    allocation_asset_class: Dict[AssetClassType, float] = Field(
        description="Porcentajes de asignación por clase de activo. Deben sumar 100.", example={"equity": 100}
    )

    @field_validator("allocation_regions", "allocation_sectors", "allocation_asset_class")
    def validate_allocations(cls, v):
        """Asegurar que todas las asignaciones sumen 100"""
        if not v:
            raise ValueError("La asignación no puede estar vacía")
        total = sum(v.values())
        if abs(total - 100) > 3:
            raise ValueError(f"Las asignaciones deben sumar 100, se obtuvo {total}")
        return v


class InstrumentResponse(InstrumentCreate):
    """Esquema para respuestas de instrumentos de la base de datos"""

    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    """Esquema para crear un usuario - adecuado para entrada de herramienta LLM"""

    clerk_user_id: str = Field(description="Identificador único del sistema de autenticación Clerk")
    display_name: Optional[str] = Field(None, description="Nombre para mostrar del usuario", max_length=255)
    years_until_retirement: Optional[int] = Field(
        None, description="Número de años hasta que el usuario planea jubilarse", ge=0, le=100
    )
    target_retirement_income: Optional[Decimal] = Field(
        None, description="Ingreso anual objetivo en la jubilación (en dólares)", ge=0, decimal_places=2
    )
    asset_class_targets: Optional[Dict[AssetClassType, float]] = Field(
        default={"equity": 70, "fixed_income": 30},
        description="Porcentajes de asignación objetivo para rebalanceo. Deben sumar 100.",
    )
    region_targets: Optional[Dict[RegionType, float]] = Field(
        default={"north_america": 50, "international": 50},
        description="Asignación geográfica objetivo para rebalanceo. Debe sumar 100.",
    )


class AccountCreate(BaseModel):
    """Esquema para crear una cuenta - adecuado para entrada de herramienta LLM"""

    account_name: str = Field(
        description="Nombre de la cuenta (p.ej., '401k', 'Roth IRA')", min_length=1, max_length=255
    )
    account_purpose: Optional[str] = Field(None, description="Propósito u objetivo de esta cuenta")
    cash_balance: Decimal = Field(
        default=Decimal("0"),
        description="Saldo en efectivo no invertido de la cuenta",
        ge=0,
        decimal_places=2,
    )
    cash_interest: Decimal = Field(
        default=Decimal("0"),
        description="Tasa de interés anual sobre el efectivo (p.ej., 0.045 para 4.5%)",
        ge=0,
        le=1,
        decimal_places=4,
    )


class PositionCreate(BaseModel):
    """Esquema para crear una posición - adecuado para entrada de herramienta LLM"""

    account_id: str = Field(description="UUID de la cuenta que sostiene esta posición")
    symbol: str = Field(description="Símbolo bursátil del instrumento", min_length=1, max_length=20)
    quantity: Decimal = Field(
        description="Número de acciones (soporta acciones fraccionarias)", gt=0, decimal_places=8
    )
    as_of_date: Optional[date] = Field(
        default_factory=date.today, description="Fecha de este snapshot de la posición"
    )


class JobCreate(BaseModel):
    """Esquema para crear un trabajo - adecuado para entrada de herramienta LLM"""

    clerk_user_id: str = Field(description="Usuario que solicita este trabajo")
    job_type: JobType = Field(description="Tipo de análisis u operación a realizar")
    request_payload: Optional[Dict] = Field(None, description="Parámetros de entrada para el trabajo")


class JobUpdate(BaseModel):
    """Esquema para actualizar el estado del trabajo - adecuado para salida de herramienta LLM"""

    status: JobStatus = Field(description="Estado actual del trabajo")
    result_payload: Optional[Dict] = Field(None, description="Resultados del trabajo completado")
    error_message: Optional[str] = Field(None, description="Detalles del error si el trabajo falló")


class PortfolioAnalysis(BaseModel):
    """Esquema para los resultados del análisis de portafolio - salida estructurada LLM"""

    total_value: Decimal = Field(description="Valor total del portafolio en dólares", decimal_places=2)
    asset_allocation: Dict[AssetClassType, float] = Field(
        description="Porcentajes actuales de asignación por clase de activo"
    )
    region_allocation: Dict[RegionType, float] = Field(
        description="Porcentajes actuales de asignación geográfica"
    )
    sector_allocation: Dict[SectorType, float] = Field(
        description="Porcentajes actuales de asignación sectorial"
    )
    risk_score: int = Field(
        description="Puntaje de riesgo de 1 (conservador) a 10 (agresivo)", ge=1, le=10
    )
    recommendations: List[str] = Field(
        description="Lista de recomendaciones accionables para el portafolio"
    )


class RebalanceRecommendation(BaseModel):
    """Esquema para recomendaciones de rebalanceo - salida estructurada LLM"""

    current_allocation: Dict[str, float] = Field(
        description="Asignación actual por símbolo del instrumento"
    )
    target_allocation: Dict[str, float] = Field(
        description="Asignación objetivo recomendada por símbolo"
    )
    trades: List[Dict] = Field(
        description="Lista de operaciones necesarias para el rebalanceo",
        example=[
            {"symbol": "SPY", "action": "sell", "quantity": 10},
            {"symbol": "BND", "action": "buy", "quantity": 50},
        ],
    )
    rationale: str = Field(description="Explicación de por qué se recomiendan estos cambios")
