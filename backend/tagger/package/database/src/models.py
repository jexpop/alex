"""
Modelos de base de datos y generadores de consultas
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, date
from decimal import Decimal
from .client import DataAPIClient
from .schemas import (
    InstrumentCreate, UserCreate, AccountCreate, 
    PositionCreate, JobCreate, JobUpdate
)


class BaseModel:
    """Clase base para modelos de base de datos"""
    
    table_name = None
    
    def __init__(self, db: DataAPIClient):
        self.db = db
        if not self.table_name:
            raise ValueError("table_name debe ser definido")
    
    def find_by_id(self, id: Any) -> Optional[Dict]:
        """Buscar un registro por ID"""
        sql = f"SELECT * FROM {self.table_name} WHERE id = :id::uuid"
        return self.db.query_one(sql, [{'name': 'id', 'value': {'stringValue': str(id)}}])
    
    def find_all(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Buscar todos los registros con paginación"""
        sql = f"SELECT * FROM {self.table_name} LIMIT :limit OFFSET :offset"
        params = [
            {'name': 'limit', 'value': {'longValue': limit}},
            {'name': 'offset', 'value': {'longValue': offset}}
        ]
        return self.db.query(sql, params)
    
    def create(self, data: Dict, returning: str = 'id') -> str:
        """Crear un nuevo registro"""
        return self.db.insert(self.table_name, data, returning=returning)
    
    def update(self, id: Any, data: Dict) -> int:
        """Actualizar un registro por ID"""
        return self.db.update(self.table_name, data, "id = :id::uuid", {'id': str(id)})
    
    def delete(self, id: Any) -> int:
        """Eliminar un registro por ID"""
        return self.db.delete(self.table_name, "id = :id::uuid", {'id': str(id)})


class Users(BaseModel):
    """Operaciones sobre la tabla de usuarios"""
    table_name = 'users'
    
    def find_by_clerk_id(self, clerk_user_id: str) -> Optional[Dict]:
        """Buscar usuario por Clerk ID"""
        sql = f"SELECT * FROM {self.table_name} WHERE clerk_user_id = :clerk_id"
        params = [{'name': 'clerk_id', 'value': {'stringValue': clerk_user_id}}]
        return self.db.query_one(sql, params)
    
    def create_user(self, clerk_user_id: str, display_name: str = None, 
                   years_until_retirement: int = None,
                   target_retirement_income: Decimal = None) -> str:
        """Crear un nuevo usuario"""
        data = {
            'clerk_user_id': clerk_user_id,
            'display_name': display_name,
            'years_until_retirement': years_until_retirement,
            'target_retirement_income': target_retirement_income
        }
        # Eliminar valores None
        data = {k: v for k, v in data.items() if v is not None}
        return self.db.insert(self.table_name, data, returning='clerk_user_id')


class Instruments(BaseModel):
    """Operaciones sobre la tabla de instrumentos"""
    table_name = 'instruments'

    def find_all(self, limit: int = None, offset: int = 0) -> List[Dict]:
        """Buscar todos los instrumentos - sin límite por defecto para autocompletado"""
        sql = f"SELECT * FROM {self.table_name} ORDER BY symbol"
        return self.db.query(sql, [])

    def find_by_symbol(self, symbol: str) -> Optional[Dict]:
        """Buscar instrumento por símbolo"""
        sql = f"SELECT * FROM {self.table_name} WHERE symbol = :symbol"
        params = [{'name': 'symbol', 'value': {'stringValue': symbol}}]
        return self.db.query_one(sql, params)
    
    def create_instrument(self, instrument: InstrumentCreate) -> str:
        """Crear un nuevo instrumento con validación"""
        # Validar usando Pydantic
        validated = instrument.model_dump()
        
        # Convertir asignaciones a cadenas JSON para el almacenamiento
        data = {
            'symbol': validated['symbol'],
            'name': validated['name'],
            'instrument_type': validated['instrument_type'],
            'allocation_regions': validated['allocation_regions'],
            'allocation_sectors': validated['allocation_sectors'],
            'allocation_asset_class': validated['allocation_asset_class']
        }
        
        return self.db.insert(self.table_name, data, returning='symbol')
    
    def find_by_type(self, instrument_type: str) -> List[Dict]:
        """Buscar todos los instrumentos de un tipo específico"""
        sql = f"SELECT * FROM {self.table_name} WHERE instrument_type = :type ORDER BY symbol"
        params = [{'name': 'type', 'value': {'stringValue': instrument_type}}]
        return self.db.query(sql, params)
    
    def search(self, query: str) -> List[Dict]:
        """Buscar instrumentos por símbolo o nombre"""
        sql = f"""
            SELECT * FROM {self.table_name} 
            WHERE LOWER(symbol) LIKE LOWER(:query) 
               OR LOWER(name) LIKE LOWER(:query)
            ORDER BY symbol
            LIMIT 20
        """
        params = [{'name': 'query', 'value': {'stringValue': f'%{query}%'}}]
        return self.db.query(sql, params)


class Accounts(BaseModel):
    """Operaciones sobre la tabla de cuentas"""
    table_name = 'accounts'
    
    def find_by_user(self, clerk_user_id: str) -> List[Dict]:
        """Buscar todas las cuentas de un usuario"""
        sql = f"""
            SELECT * FROM {self.table_name} 
            WHERE clerk_user_id = :user_id 
            ORDER BY created_at DESC
        """
        params = [{'name': 'user_id', 'value': {'stringValue': clerk_user_id}}]
        return self.db.query(sql, params)
    
    def create_account(self, clerk_user_id: str, account_name: str,
                      account_purpose: str = None, cash_balance: Decimal = Decimal('0'),
                      cash_interest: Decimal = Decimal('0')) -> str:
        """Crear una nueva cuenta"""
        data = {
            'clerk_user_id': clerk_user_id,
            'account_name': account_name,
            'account_purpose': account_purpose,
            'cash_balance': cash_balance,
            'cash_interest': cash_interest
        }
        return self.db.insert(self.table_name, data, returning='id')


class Positions(BaseModel):
    """Operaciones sobre la tabla de posiciones"""
    table_name = 'positions'
    
    def find_by_account(self, account_id: str) -> List[Dict]:
        """Buscar todas las posiciones en una cuenta"""
        sql = f"""
            SELECT p.*, i.name as instrument_name, i.instrument_type, i.current_price
            FROM {self.table_name} p
            JOIN instruments i ON p.symbol = i.symbol
            WHERE p.account_id = :account_id::uuid
            ORDER BY p.symbol
        """
        params = [{'name': 'account_id', 'value': {'stringValue': account_id}}]
        return self.db.query(sql, params)
    
    def get_portfolio_value(self, account_id: str) -> Dict:
        """Calcular el valor total del portafolio usando precios actuales de la tabla de instrumentos"""
        sql = """
            SELECT 
                COUNT(DISTINCT p.symbol) as num_positions,
                SUM(p.quantity * i.current_price) as total_value,
                SUM(p.quantity) as total_shares
            FROM positions p
            JOIN instruments i ON p.symbol = i.symbol
            WHERE p.account_id = :account_id::uuid
        """
        params = [
            {'name': 'account_id', 'value': {'stringValue': account_id}}
        ]
        result = self.db.query_one(sql, params)
        if result:
            return {
                'num_positions': result.get('num_positions', 0),
                'total_value': float(result.get('total_value', 0)) if result.get('total_value') else 0,
                'total_shares': float(result.get('total_shares', 0)) if result.get('total_shares') else 0
            }
        return {'num_positions': 0, 'total_value': 0, 'total_shares': 0}
    
    def add_position(self, account_id: str, symbol: str, quantity: Decimal) -> str:
        """Agregar o actualizar una posición"""
        # Utilizar UPSERT para manejar posiciones existentes
        sql = """
            INSERT INTO positions (account_id, symbol, quantity, as_of_date)
            VALUES (:account_id::uuid, :symbol, :quantity::numeric, :as_of_date::date)
            ON CONFLICT (account_id, symbol) 
            DO UPDATE SET 
                quantity = EXCLUDED.quantity,
                as_of_date = EXCLUDED.as_of_date,
                updated_at = NOW()
            RETURNING id
        """
        params = [
            {'name': 'account_id', 'value': {'stringValue': account_id}},
            {'name': 'symbol', 'value': {'stringValue': symbol}},
            {'name': 'quantity', 'value': {'stringValue': str(quantity)}},
            {'name': 'as_of_date', 'value': {'stringValue': date.today().isoformat()}}
        ]
        response = self.db.execute(sql, params)
        if response.get('records'):
            return response['records'][0][0].get('stringValue')
        return None


class Jobs(BaseModel):
    """Operaciones sobre la tabla de trabajos (jobs)"""
    table_name = 'jobs'
    
    def create_job(self, clerk_user_id: str, job_type: str, 
                  request_payload: Dict = None) -> str:
        """Crear un nuevo trabajo"""
        data = {
            'clerk_user_id': clerk_user_id,
            'job_type': job_type,
            'status': 'pending',
            'request_payload': request_payload
        }
        return self.db.insert(self.table_name, data, returning='id')
    
    def update_status(self, job_id: str, status: str, error_message: str = None) -> int:
        """Actualizar el estado de un trabajo"""
        data = {'status': status}
        
        if status == 'running':
            data['started_at'] = datetime.utcnow()
        elif status in ['completed', 'failed']:
            data['completed_at'] = datetime.utcnow()
        
        if error_message:
            data['error_message'] = error_message
        
        return self.db.update(self.table_name, data, "id = :id::uuid", {'id': job_id})
    
    def update_report(self, job_id: str, report_payload: Dict) -> int:
        """Actualizar trabajo con el análisis del agente Reporter"""
        data = {'report_payload': report_payload}
        return self.db.update(self.table_name, data, "id = :id::uuid", {'id': job_id})
    
    def update_charts(self, job_id: str, charts_payload: Dict) -> int:
        """Actualizar trabajo con los datos de visualización del agente Charter"""
        data = {'charts_payload': charts_payload}
        return self.db.update(self.table_name, data, "id = :id::uuid", {'id': job_id})
    
    def update_retirement(self, job_id: str, retirement_payload: Dict) -> int:
        """Actualizar trabajo con las proyecciones del agente Retirement"""
        data = {'retirement_payload': retirement_payload}
        return self.db.update(self.table_name, data, "id = :id::uuid", {'id': job_id})
    
    def update_summary(self, job_id: str, summary_payload: Dict) -> int:
        """Actualizar trabajo con el resumen final del Planner"""
        data = {'summary_payload': summary_payload}
        return self.db.update(self.table_name, data, "id = :id::uuid", {'id': job_id})
    
    def find_by_user(self, clerk_user_id: str, status: str = None, 
                    limit: int = 20) -> List[Dict]:
        """Buscar trabajos para un usuario"""
        if status:
            sql = f"""
                SELECT * FROM {self.table_name}
                WHERE clerk_user_id = :user_id AND status = :status
                ORDER BY created_at DESC
                LIMIT :limit
            """
            params = [
                {'name': 'user_id', 'value': {'stringValue': clerk_user_id}},
                {'name': 'status', 'value': {'stringValue': status}},
                {'name': 'limit', 'value': {'longValue': limit}}
            ]
        else:
            sql = f"""
                SELECT * FROM {self.table_name}
                WHERE clerk_user_id = :user_id
                ORDER BY created_at DESC
                LIMIT :limit
            """
            params = [
                {'name': 'user_id', 'value': {'stringValue': clerk_user_id}},
                {'name': 'limit', 'value': {'longValue': limit}}
            ]
        
        return self.db.query(sql, params)


class Database:
    """Interfaz principal de la base de datos que proporciona acceso a todos los modelos"""
    
    def __init__(self, cluster_arn: str = None, secret_arn: str = None,
                 database: str = None, region: str = None):
        """Inicializar base de datos con todas las clases de modelos"""
        self.client = DataAPIClient(cluster_arn, secret_arn, database, region)
        
        # Inicializar todos los modelos
        self.users = Users(self.client)
        self.instruments = Instruments(self.client)
        self.accounts = Accounts(self.client)
        self.positions = Positions(self.client)
        self.jobs = Jobs(self.client)
    
    def execute_raw(self, sql: str, parameters: List[Dict] = None) -> Dict:
        """Ejecutar SQL crudo para consultas complejas"""
        return self.client.execute(sql, parameters)
    
    def query_raw(self, sql: str, parameters: List[Dict] = None) -> List[Dict]:
        """Ejecutar consulta SELECT cruda"""
        return self.client.query(sql, parameters)