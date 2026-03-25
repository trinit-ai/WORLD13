.PHONY: init sim api dashboard test install shadow-init shadow-sim shadow-api

init:
	python3 scripts/init_world.py

sim:
	python3 -c "import asyncio; from engine.simulation import WorldSimulation; asyncio.run(WorldSimulation().run())"

api:
	uvicorn api.app:app --reload --port 8001

dashboard:
	cd dashboard && npm start

test:
	python3 -m pytest tests/ -v

shadow-init:
	python3 scripts/init_shadow_world.py

shadow-sim:
	WORLD13_MODE=shadow python3 -c "import asyncio; from engine.simulation import WorldSimulation; asyncio.run(WorldSimulation().run())"

shadow-api:
	WORLD13_MODE=shadow uvicorn api.app:app --reload --port 8002

install:
	pip3 install fastapi uvicorn anthropic python-dotenv pytest pytest-asyncio
	cd dashboard && npm install
