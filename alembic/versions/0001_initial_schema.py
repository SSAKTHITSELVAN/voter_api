"""Initial schema with PostGIS

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
import geoalchemy2
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostGIS extension (try to create, but don't fail if permissions are insufficient)
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    except Exception:
        # PostGIS extension should be created manually by superuser if this fails
        pass

    # ── ENUM types ────────────────────────────────────────────────────────────
    userrole = postgresql.ENUM(
        "SUPER_ADMIN", "ADMIN", "FIELD_USER", name="userrole"
    )
    userrole.create(op.get_bind(), checkfirst=True)

    housetype = postgresql.ENUM("INDIVIDUAL", "APARTMENT", name="housetype")
    housetype.create(op.get_bind(), checkfirst=True)

    gendertype = postgresql.ENUM("MALE", "FEMALE", "OTHER", name="gendertype")
    gendertype.create(op.get_bind(), checkfirst=True)

    verificationstatus = postgresql.ENUM("MATCHED", "MISMATCH", name="verificationstatus")
    verificationstatus.create(op.get_bind(), checkfirst=True)

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("phone", sa.String(20), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("SUPER_ADMIN", "ADMIN", "FIELD_USER", name="userrole"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_phone", "users", ["phone"])

    # ── buildings ─────────────────────────────────────────────────────────────
    op.create_table(
        "buildings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("address_text", sa.Text, nullable=True),
        sa.Column("total_floors", sa.Integer, nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── units ─────────────────────────────────────────────────────────────────
    op.create_table(
        "units",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("building_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("flat_number", sa.String(30), nullable=False),
        sa.Column("floor_number", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_units_building_id", "units", ["building_id"])

    # ── households ────────────────────────────────────────────────────────────
    op.create_table(
        "households",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("latitude", sa.Float, nullable=False),
        sa.Column("longitude", sa.Float, nullable=False),
        sa.Column("geog", geoalchemy2.Geography(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column("address_text", sa.Text, nullable=True),
        sa.Column("landmark_description", sa.Text, nullable=True),
        sa.Column("house_type", sa.Enum("INDIVIDUAL", "APARTMENT", name="housetype"), nullable=False),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("units.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_households_created_by", "households", ["created_by"])
    op.create_index("ix_households_unit_id", "households", ["unit_id"])
    # GIST spatial index for fast geo queries
    op.execute("CREATE INDEX ix_households_geog ON households USING GIST (geog);")

    # ── household_images ──────────────────────────────────────────────────────
    op.create_table(
        "household_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image_url", sa.String(512), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_household_images_household_id", "household_images", ["household_id"])

    # ── persons ───────────────────────────────────────────────────────────────
    op.create_table(
        "persons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("households.id", ondelete="CASCADE"), nullable=False),
        sa.Column("age", sa.Integer, nullable=True),
        sa.Column("gender", sa.Enum("MALE", "FEMALE", "OTHER", name="gendertype"), nullable=True),
        sa.Column("is_voter", sa.Boolean, default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_persons_household_id", "persons", ["household_id"])

    # ── collection_records ────────────────────────────────────────────────────
    op.create_table(
        "collection_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("households.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("collected_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("total_people", sa.Integer, nullable=False, default=0),
        sa.Column("total_voters", sa.Integer, nullable=False, default=0),
        sa.Column("raw_data_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_collection_records_household_id", "collection_records", ["household_id"])
    op.create_index("ix_collection_records_collected_by", "collection_records", ["collected_by"])

    # ── verification_records ──────────────────────────────────────────────────
    op.create_table(
        "verification_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("household_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("households.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.Enum("MATCHED", "MISMATCH", name="verificationstatus"), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_verification_records_household_id", "verification_records", ["household_id"])
    op.create_index("ix_verification_records_verified_by", "verification_records", ["verified_by"])


def downgrade() -> None:
    op.drop_table("verification_records")
    op.drop_table("collection_records")
    op.drop_table("persons")
    op.drop_table("household_images")
    op.drop_table("households")
    op.drop_table("units")
    op.drop_table("buildings")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS verificationstatus;")
    op.execute("DROP TYPE IF EXISTS gendertype;")
    op.execute("DROP TYPE IF EXISTS housetype;")
    op.execute("DROP TYPE IF EXISTS userrole;")
