.PHONY: init sim api dashboard test install

init:
	python scripts/init_world.py

sim:
	python -c "import asyncio; from engine.simulation import WorldSimulation; asyncio.run(WorldSimulation().run())"

api:
	uvicorn api.app:app --reload --port 8001

dashboard:
	cd dashboard && npm start

test:
	pytest tests/ -v

install:
	pip install fastapi uvicorn anthropic python-dotenv pytest pytest-asyncio
	cd dashboard && npm install
