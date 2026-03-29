.PHONY: init sim api dashboard test install shadow-init shadow-sim shadow-api duck theatres theatre voynich rits rits-validate talent talent-dry marriage marriage-dry world world-init world-fast

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

duck:
	python3 theatres/run_theatre.py --theatre enlightened_duck

theatres:
	python3 theatres/run_theatre.py --list

theatre:
	python3 theatres/run_theatre.py --theatre $(name)

voynich:
	python3 theatres/run_theatre.py --theatre digital_voynich

calibration:
	python3 theatres/competence_calibration/run.py

calibration-dry:
	python3 theatres/competence_calibration/run.py --dry-run

marriage:
	python3 theatres/marriage/run.py

marriage-dry:
	python3 theatres/marriage/run.py --dry-run

talent:
	python3 theatres/talent_retention/run.py

talent-dry:
	python3 theatres/talent_retention/run.py --dry-run

world-init:
	python3 scripts/init_world_mode.py

world:
	WORLD13_MODE=world WORLD13_TICK_SECONDS=300 WORLD13_SESSIONS_PER_TICK=1 python3 -c "import asyncio; from engine.simulation import WorldSimulation; asyncio.run(WorldSimulation('data/world13_world.db').run())"

world-fast:
	WORLD13_MODE=world WORLD13_TICK_SECONDS=30 WORLD13_SESSIONS_PER_TICK=2 python3 -c "import asyncio; from engine.simulation import WorldSimulation; asyncio.run(WorldSimulation('data/world13_world.db').run())"

rits:
	WORLD13_MODE=rits python3 -c "import asyncio; from engine.rits import RITSSimulation; asyncio.run(RITSSimulation().run())"

rits-validate:
	python3 -c "from engine.rits import RITSCoordinates, RITSAgent, RITSSimulation; print('RITS 13-system stack OK')"

install:
	pip3 install fastapi uvicorn anthropic python-dotenv pytest pytest-asyncio pyyaml
	cd dashboard && npm install
