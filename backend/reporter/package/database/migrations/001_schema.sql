-- Esquema de la base de datos de Alex Financial Planner
-- Versión: 001
-- Descripción: Esquema inicial para una plataforma de planificación financiera multiusuario

-- Habilitar la extensión UUID para gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Tabla mínima de usuarios (Clerk maneja la autenticación)
CREATE TABLE IF NOT EXISTS users (
    clerk_user_id VARCHAR(255) PRIMARY KEY,
    display_name VARCHAR(255),
    years_until_retirement INTEGER,
    target_retirement_income DECIMAL(12,2),  -- Objetivo de ingreso anual
    
    -- Objetivos de asignación para el rebalanceo (almacenados en JSON)
    asset_class_targets JSONB DEFAULT '{"equity": 70, "fixed_income": 30}',
    region_targets JSONB DEFAULT '{"north_america": 50, "international": 50}',
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Datos de referencia para instrumentos
CREATE TABLE IF NOT EXISTS instruments (
    symbol VARCHAR(20) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    instrument_type VARCHAR(50),  -- 'equity', 'etf', 'mutual_fund', 'bond_fund'
    current_price DECIMAL(12,4),  -- Precio actual para cálculos de portafolio
    
    -- Porcentajes de asignación (0-100, almacenados en JSON)
    allocation_regions JSONB DEFAULT '{}',      -- {"north_america": 60, "europe": 20, "asia": 20}
    allocation_sectors JSONB DEFAULT '{}',      -- {"technology": 30, "healthcare": 20, ...}
    allocation_asset_class JSONB DEFAULT '{}',  -- {"equity": 80, "fixed_income": 20}
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Cuentas de inversión del usuario
CREATE TABLE IF NOT EXISTS accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    clerk_user_id VARCHAR(255) REFERENCES users(clerk_user_id) ON DELETE CASCADE,
    account_name VARCHAR(255) NOT NULL,     -- "401k", "Roth IRA"
    account_purpose TEXT,                    -- "Ahorro para retiro a largo plazo"
    cash_balance DECIMAL(12,2) DEFAULT 0,   -- Efectivo no invertido
    cash_interest DECIMAL(5,4) DEFAULT 0,   -- Tasa de interés anual (0.045 = 4.5%)
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Posiciones actuales en cada cuenta
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    account_id UUID REFERENCES accounts(id) ON DELETE CASCADE,
    symbol VARCHAR(20) REFERENCES instruments(symbol),
    quantity DECIMAL(20,8) NOT NULL,        -- Soporta acciones fraccionales
    as_of_date DATE DEFAULT CURRENT_DATE,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Garantizar que no haya posiciones duplicadas por cuenta
    UNIQUE(account_id, symbol)
);

-- Seguimiento de tareas para análisis asíncrono
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    clerk_user_id VARCHAR(255) REFERENCES users(clerk_user_id) ON DELETE CASCADE,
    job_type VARCHAR(50) NOT NULL,          -- 'portfolio_analysis', 'rebalance', 'projection'
    status VARCHAR(20) DEFAULT 'pending',    -- 'pending', 'running', 'completed', 'failed'
    request_payload JSONB,                   -- Parámetros de entrada
    
    -- Campos separados para los resultados de cada agente (no es necesario combinar)
    report_payload JSONB,                    -- Análisis markdown del agente "Reporter"
    charts_payload JSONB,                    -- Datos de visualización del agente "Charter"
    retirement_payload JSONB,                -- Proyecciones del agente de retiro
    summary_payload JSONB,                   -- Resumen/final de metadatos del planificador
    
    error_message TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Crear índices para consultas comunes
CREATE INDEX IF NOT EXISTS idx_accounts_user ON accounts(clerk_user_id);
CREATE INDEX IF NOT EXISTS idx_positions_account ON positions(account_id);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(clerk_user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);

-- Crear función trigger para actualizar updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Añadir triggers de actualización a las tablas con updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_instruments_updated_at BEFORE UPDATE ON instruments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_accounts_updated_at BEFORE UPDATE ON accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_positions_updated_at BEFORE UPDATE ON positions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();