"""
Wrapper del Cliente Aurora Data API
Proporciona una interfaz sencilla para operaciones de base de datos
"""

import boto3
import json
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import date, datetime
from decimal import Decimal
from botocore.exceptions import ClientError
import logging

# Intentar cargar el archivo .env si existe
try:
    from dotenv import load_dotenv

    load_dotenv(override=True)
except ImportError:
    pass  # dotenv no está instalado, continuar sin él

logger = logging.getLogger(__name__)


class DataAPIClient:
    """Wrapper para AWS RDS Data API para simplificar operaciones de base de datos"""

    def __init__(
        self,
        cluster_arn: str = None,
        secret_arn: str = None,
        database: str = None,
        region: str = None,
    ):
        """
        Inicializar el cliente Data API

        Args:
            cluster_arn: ARN del clúster de Aurora (o desde env AURORA_CLUSTER_ARN)
            secret_arn: ARN de Secrets Manager (o desde env AURORA_SECRET_ARN)
            database: Nombre de la base de datos (o desde env AURORA_DATABASE)
            region: Región de AWS (o desde env AWS_REGION)
        """
        self.cluster_arn = cluster_arn or os.environ.get("AURORA_CLUSTER_ARN")
        self.secret_arn = secret_arn or os.environ.get("AURORA_SECRET_ARN")
        self.database = database or os.environ.get("AURORA_DATABASE", "alex")

        if not self.cluster_arn or not self.secret_arn:
            raise ValueError(
                "Falta la configuración requerida de Aurora. "
                "Establezca las variables de entorno AURORA_CLUSTER_ARN y AURORA_SECRET_ARN."
            )

        self.region = os.environ.get("DEFAULT_AWS_REGION", "us-east-1")
        self.client = boto3.client("rds-data", region_name=self.region)

    def execute(self, sql: str, parameters: List[Dict] = None) -> Dict:
        """
        Ejecuta una sentencia SQL

        Args:
            sql: Sentencia SQL a ejecutar
            parameters: Lista opcional de parámetros para consulta preparada

        Returns:
            Respuesta de Data API
        """
        try:
            kwargs = {
                "resourceArn": self.cluster_arn,
                "secretArn": self.secret_arn,
                "database": self.database,
                "sql": sql,
                "includeResultMetadata": True,  # Incluir nombres de columna
            }

            if parameters:
                kwargs["parameters"] = parameters

            response = self.client.execute_statement(**kwargs)
            return response

        except ClientError as e:
            logger.error(f"Error de base de datos: {e}")
            raise

    def query(self, sql: str, parameters: List[Dict] = None) -> List[Dict]:
        """
        Ejecuta una consulta SELECT y retorna resultados como lista de diccionarios

        Args:
            sql: Sentencia SELECT
            parameters: Parámetros opcionales

        Returns:
            Lista de diccionarios con nombres de columnas como claves
        """
        response = self.execute(sql, parameters)

        if "records" not in response:
            return []

        # Extraer nombres de columnas
        columns = [col["name"] for col in response.get("columnMetadata", [])]

        # Convertir registros a diccionarios
        results = []
        for record in response["records"]:
            row = {}
            for i, col in enumerate(columns):
                value = self._extract_value(record[i])
                row[col] = value
            results.append(row)

        return results

    def query_one(self, sql: str, parameters: List[Dict] = None) -> Optional[Dict]:
        """
        Ejecuta una consulta SELECT y retorna el primer resultado

        Args:
            sql: Sentencia SELECT
            parameters: Parámetros opcionales

        Returns:
            Diccionario con nombres de columnas como claves, o None si no hay resultados
        """
        results = self.query(sql, parameters)
        return results[0] if results else None

    def insert(self, table: str, data: Dict, returning: str = None) -> str:
        """
        Inserta un registro en una tabla

        Args:
            table: Nombre de la tabla
            data: Diccionario de nombres de columnas y valores
            returning: Columna a retornar (ej. 'id', 'clerk_user_id')

        Returns:
            Valor de la columna retornada si se especificó
        """
        columns = list(data.keys())
        placeholders = []

        # Verifica si alguna columna necesita 'type casting'
        for col in columns:
            if isinstance(data[col], (dict, list)):
                placeholders.append(f":{col}::jsonb")
            elif isinstance(data[col], Decimal):
                placeholders.append(f":{col}::numeric")
            elif isinstance(data[col], date) and not isinstance(data[col], datetime):
                placeholders.append(f":{col}::date")
            elif isinstance(data[col], datetime):
                placeholders.append(f":{col}::timestamp")
            else:
                placeholders.append(f":{col}")

        sql = f"""
            INSERT INTO {table} ({", ".join(columns)})
            VALUES ({", ".join(placeholders)})
        """

        # Añadir cláusula RETURNING si se especificó
        if returning:
            sql += f" RETURNING {returning}"

        parameters = self._build_parameters(data)
        response = self.execute(sql, parameters)

        # Retorna el valor si se usó RETURNING
        if returning and response.get("records"):
            return self._extract_value(response["records"][0][0])
        return None

    def update(self, table: str, data: Dict, where: str, where_params: Dict = None) -> int:
        """
        Actualiza registros en una tabla

        Args:
            table: Nombre de la tabla
            data: Diccionario de columnas a actualizar
            where: Cláusula WHERE (sin la palabra WHERE)
            where_params: Parámetros para la cláusula WHERE

        Returns:
            Número de filas afectadas
        """
        # Construye la cláusula SET con 'type casting' cuando sea necesario
        set_parts = []
        for col, val in data.items():
            if isinstance(val, (dict, list)):
                set_parts.append(f"{col} = :{col}::jsonb")
            elif isinstance(val, Decimal):
                set_parts.append(f"{col} = :{col}::numeric")
            elif isinstance(val, date) and not isinstance(val, datetime):
                set_parts.append(f"{col} = :{col}::date")
            elif isinstance(val, datetime):
                set_parts.append(f"{col} = :{col}::timestamp")
            else:
                set_parts.append(f"{col} = :{col}")

        set_clause = ", ".join(set_parts)

        sql = f"""
            UPDATE {table}
            SET {set_clause}
            WHERE {where}
        """

        # Combina los parámetros de data y where
        all_params = {**data, **(where_params or {})}
        parameters = self._build_parameters(all_params)

        response = self.execute(sql, parameters)
        return response.get("numberOfRecordsUpdated", 0)

    def delete(self, table: str, where: str, where_params: Dict = None) -> int:
        """
        Elimina registros de una tabla

        Args:
            table: Nombre de la tabla
            where: Cláusula WHERE (sin la palabra WHERE)
            where_params: Parámetros para la cláusula WHERE

        Returns:
            Número de filas eliminadas
        """
        sql = f"DELETE FROM {table} WHERE {where}"
        parameters = self._build_parameters(where_params) if where_params else None

        response = self.execute(sql, parameters)
        return response.get("numberOfRecordsUpdated", 0)

    def begin_transaction(self) -> str:
        """Inicia una transacción de base de datos"""
        response = self.client.begin_transaction(
            resourceArn=self.cluster_arn, secretArn=self.secret_arn, database=self.database
        )
        return response["transactionId"]

    def commit_transaction(self, transaction_id: str):
        """Confirma una transacción de base de datos"""
        self.client.commit_transaction(
            resourceArn=self.cluster_arn, secretArn=self.secret_arn, transactionId=transaction_id
        )

    def rollback_transaction(self, transaction_id: str):
        """Revierte una transacción de base de datos"""
        self.client.rollback_transaction(
            resourceArn=self.cluster_arn, secretArn=self.secret_arn, transactionId=transaction_id
        )

    def _build_parameters(self, data: Dict) -> List[Dict]:
        """Convierte un diccionario al formato de parámetros de Data API"""
        if not data:
            return []

        parameters = []
        for key, value in data.items():
            param = {"name": key}

            if value is None:
                param["value"] = {"isNull": True}
            elif isinstance(value, bool):
                param["value"] = {"booleanValue": value}
            elif isinstance(value, int):
                param["value"] = {"longValue": value}
            elif isinstance(value, float):
                param["value"] = {"doubleValue": value}
            elif isinstance(value, Decimal):
                param["value"] = {"stringValue": str(value)}
            elif isinstance(value, (date, datetime)):
                param["value"] = {"stringValue": value.isoformat()}
            elif isinstance(value, dict):
                param["value"] = {"stringValue": json.dumps(value)}
            elif isinstance(value, list):
                param["value"] = {"stringValue": json.dumps(value)}
            else:
                param["value"] = {"stringValue": str(value)}

            parameters.append(param)

        return parameters

    def _extract_value(self, field: Dict) -> Any:
        """Extrae el valor desde la respuesta del campo de Data API"""
        if field.get("isNull"):
            return None
        elif "booleanValue" in field:
            return field["booleanValue"]
        elif "longValue" in field:
            return field["longValue"]
        elif "doubleValue" in field:
            return field["doubleValue"]
        elif "stringValue" in field:
            value = field["stringValue"]
            # Intentar interpretar como JSON si parece ser JSON
            if value and value[0] in ["{", "["]:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    pass
            return value
        elif "blobValue" in field:
            return field["blobValue"]
        else:
            return None
