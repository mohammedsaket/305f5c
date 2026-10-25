.PHONY: data test api web docker

data:
	cd backend && python3 -m daymark.build

test:
	cd backend && python3 -m pytest -q

api:
	cd backend && python3 -m uvicorn daymark.api:app --reload --port 8000

web:
	cd frontend && npm run dev

docker:
	docker compose up --build
