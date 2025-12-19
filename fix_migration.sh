#!/bin/bash
# Quick fix script to restore all database tables

echo "Step 1: Stamping database to version before survey migration..."
alembic stamp f9218dd57616

echo "Step 2: Running all migrations from that point..."
alembic upgrade head

echo "Done! All tables should now be restored."









