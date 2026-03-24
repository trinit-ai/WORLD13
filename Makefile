.PHONY: init sim api dashboard test install

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

install:
	pip3 install fastapi uvicorn anthropic python-dotenv pytest pytest-asyncio
	cd dashboard && npm install
