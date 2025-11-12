# BotFactory Monorepo

שלושה שירותים: gateway (Webhook+Dashboard), botshop (FastAPI+PTB), slhton (בורסה/ארנק).
הוראות הרצה לוקאל: docker compose -f infra/docker-compose.yml up --build.

פריסה ל-Railway: צור 3 Services, כל אחד עם Root Directory:
- services/gateway
- services/botshop
- services/slhton

ייבא Variables מתוך .env.example (התאם טוקנים, כתובת PUBLIC_BASE_URL, DB וכו').
