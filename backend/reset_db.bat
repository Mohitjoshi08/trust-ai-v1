del /f /q trace_ai.db
del /f /q alembic\versions\*
.venv\Scripts\alembic.exe revision --autogenerate -m "Initial"
.venv\Scripts\alembic.exe upgrade head
