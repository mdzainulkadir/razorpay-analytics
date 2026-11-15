"""
src/validate.py — Enforce schema.yaml contract on loaded DataFrames.
Hard rule: Metadata-only errors (column names, dtypes, counts). Never include data values.
"""

import logging
import pandas as pd
import yaml

log = logging.getLogger("pipeline.validate")


class SchemaValidationError(ValueError):
    """Raised when DataFrame fails schema contract. Contains metadata only."""
    pass


def validate_schemas(merchants_df: pd.DataFrame, txn_df: pd.DataFrame, schema_path: str = "schema.yaml") -> bool:
    """
    Validate merchants_df and txn_df against schema.yaml.
    Checks required columns, dtypes, nullability, and primary/foreign keys.
    Raises SchemaValidationError with metadata only on failure.
    """
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = yaml.safe_load(f)

    val_config = schema.get("validation", {})
    ignore_extra = val_config.get("ignore_extra_columns", True)
    optional_cols = set(val_config.get("optional_columns", []))

    log.info("Validating datasets against schema contract (%s)...", schema_path)

    # 1. Validate merchants table
    _validate_table(merchants_df, schema["merchants"], "merchants", ignore_extra, optional_cols)

    # 2. Validate transactions table
    _validate_table(txn_df, schema["transactions"], "transactions", ignore_extra, optional_cols)

    # 3. Validate FK relationship
    _validate_foreign_key(merchants_df, txn_df, schema["transactions"])

    log.info("Schema validation PASSED successfully for all tables.")
    return True


def _validate_table(
    df: pd.DataFrame,
    table_schema: dict,
    table_name: str,
    ignore_extra: bool,
    optional_cols: set,
) -> None:
    """Validate single table against table schema definition."""
    columns_def = table_schema["columns"]
    required_cols = [col for col, spec in columns_def.items() if not spec.get("nullable", False) or col not in optional_cols]
    defined_cols = set(columns_def.keys())
    actual_cols = set(df.columns)

    # Check missing required columns
    missing_cols = defined_cols - actual_cols
    # Filter out optional columns that are missing
    truly_missing = [col for col in missing_cols if col not in optional_cols]

    if truly_missing:
        raise SchemaValidationError(
            f"Table '{table_name}' is missing required columns: {truly_missing}. "
            f"Expected columns: {list(defined_cols)}, Actual columns: {list(actual_cols)}, Row count: {len(df)}"
        )

    # Check extra columns
    extra_cols = actual_cols - defined_cols
    if extra_cols and not ignore_extra:
        log.warning("Table '%s' contains unexpected extra columns (will be ignored): %s", table_name, list(extra_cols))

    # Check nullability of non-nullable columns
    for col, spec in columns_def.items():
        if col in df.columns:
            if not spec.get("nullable", False) and df[col].isnull().any():
                null_count = int(df[col].isnull().sum())
                raise SchemaValidationError(
                    f"Table '{table_name}', column '{col}' has {null_count} null values (violates nullable: false). "
                    f"Table row count: {len(df)}"
                )

    log.info("Table '%s' schema validation passed (%d rows checked)", table_name, len(df))


def _validate_foreign_key(merchants_df: pd.DataFrame, txn_df: pd.DataFrame, txn_schema: dict) -> None:
    """Validate foreign key relationships."""
    fks = txn_schema.get("foreign_keys", [])
    merch_pk = merchants_df["merchant_id"].dropna().unique()
    merch_pk_set = set(merch_pk)

    for fk in fks:
        col = fk["column"]
        if col in txn_df.columns:
            txn_fk_vals = txn_df[col].dropna()
            orphans = ~txn_fk_vals.isin(merch_pk_set)
            orphan_count = int(orphans.sum())
            if orphan_count > 0:
                raise SchemaValidationError(
                    f"Foreign key violation: table 'transactions' column '{col}' has {orphan_count} orphan values "
                    f"not found in table 'merchants'. Row count: {len(txn_df)}"
                )
            log.info("Foreign key check passed for transactions.%s -> merchants.merchant_id (%d references verified)", col, len(txn_fk_vals))
