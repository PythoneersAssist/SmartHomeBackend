# SmartHomeBackend

A modular and scalable backend for Smart Home systems built with FastAPI. This project provides a robust API to manage users, homes, devices, rooms, energy consumption, and automations.

## 🚀 Features

### Implemented

- **Authentication**: OAuth2 password flow with JWT Bearer tokens. Supports login via username or email.
- **User Management**: User registration with email/password validation, profile retrieval, and account updates (username, email, password).
- **House Management**: Full CRUD for households — create, list, get by ID (with rooms), update name/description. Delete endpoint is defined but not yet implemented.

### Planned (Stubbed Out)

- **Device Management**: CRUD endpoints defined but not wired into the application.
- **Room Management**: Functions scaffolded (create, list, get, update, delete) but no router configured.
- **Energy Monitoring**: Functions scaffolded for tracking energy usage at household, room, and device levels.
- **Automations**: Functions scaffolded for creating and managing automation routines.
- **Notifications**: Communication function scaffolded.

## 🛠️ Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) with [fastapi-utils](https://fastapi-utils.davidmontague.xyz/) (class-based views)
- **ORM**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/)
- **Database**: SQLite (`database.db`)
- **Validation**: [Pydantic v2](https://docs.pydantic.dev/)
- **Authentication**: OAuth2 + JWT ([python-jose](https://github.com/mpdavis/python-jose) / [PyJWT](https://pyjwt.readthedocs.io/))
- **Password Hashing**: bcrypt via [passlib](https://passlib.readthedocs.io/)
- **Server**: [Uvicorn](https://www.uvicorn.org/)
- **Testing**: [pytest](https://docs.pytest.org/)

## 📂 Project Structure

```text
├── auth/               # Authentication (login, token generation, current user dependency)
├── automations/        # Automation routines (stubbed)
├── database/
│   ├── database.py     # SQLAlchemy engine, session, and Base setup
│   ├── models.py       # ORM models: User, House, Room, Device, Automation
│   └── enums.py        # FloorType, DeviceType, AutomationTriggerType enums
├── devices/            # Device endpoints and models (stubbed, not wired)
├── energy/             # Energy usage tracking (stubbed)
├── house/              # Household management endpoints and models
├── notifications/      # Notification service (stubbed)
├── rooms/              # Room management (stubbed)
├── users/              # User registration, profile, and device listing
├── utils/
│   ├── security.py     # JWT creation, password hashing/verification
│   ├── validation.py   # Email and password format validators
│   └── device_parameters.py  # Default parameter templates for device types
├── tests/              # pytest test suite (auth, users, house)
├── main.py             # Application entry point
├── pytest.ini          # pytest configuration
├── requirements.txt    # Python dependencies
└── README.md
```

## 📡 API Endpoints

### Active Routes

| Module | Method | Path | Auth | Description |
|--------|--------|------|:----:|-------------|
| Root | GET | `/` | — | Health check (returns `"OK"`) |
| Auth | POST | `/token` | — | Login with username or email, returns JWT |
| Users | POST | `/user/create` | — | Register a new user |
| Users | PATCH | `/user/update/` | ✔ | Update current user's profile |
| Users | GET | `/user/get` | ✔ | Get current user's details |
| Users | GET | `/user/get_devices` | ✔ | List all devices across user's houses |
| House | POST | `/home/create` | ✔ | Create a new house |
| House | GET | `/home/get` | ✔ | List all houses for the current user |
| House | GET | `/home/get_id/{house_id}` | ✔ | Get house details with rooms by UUID |
| House | PUT | `/home/update` | ✔ | Update house name or description |
| House | DELETE | `/home/delete` | — | Delete a house (stub — not implemented) |

### Defined but Not Wired

| Module | Endpoints | Status |
|--------|-----------|--------|
| Devices | create, get, get_id, update, delete | Router defined, not included in app |
| Rooms | create, list, get, update, delete | Functions only, no router |
| Energy | get by household, room, device | Functions only, no router |
| Automations | create, list, get, update, delete | Functions only, no router |
| Notifications | communicate | Function only, no router |

## 🗃️ Database Schema

### User
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Primary key |
| `username` | String | Required |
| `email` | String | Required |
| `password` | String | bcrypt hash |
| `registered_at` | String | Timestamp |

### House
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Primary key |
| `name` | String | Required, unique per user |
| `description` | String | Optional |
| `user_id` | UUID | FK → `users.id` |

### Room
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Primary key |
| `name` | String | Required |
| `floor` | Enum(`FloorType`) | ENTRANCE, FLOOR_1–FLOOR_5 |
| `house_id` | UUID | FK → `houses.id` |

### Device
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Primary key |
| `name` | String | Required |
| `type` | Enum(`DeviceType`) | 22 types (LIGHT, THERMOSTAT, etc.) |
| `parameters` | JSON | Device-specific settings |
| `room_id` | UUID | FK → `rooms.id` |

### Automation
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID | Primary key |
| `name` | String | Required |
| `trigger_type` | Enum | TIME, TEMPERATURE, LUX |
| `trigger_value` | Enum | Trigger threshold |
| `execution_day` | Integer | Optional |
| `device_id` | UUID | FK → `devices.id` |

## ⚙️ Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd smarthome-backend
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**:
   Create a `.env` file in the root directory with the following variables:
   ```env
   SECRET_KEY=<your-secret-key>
   ALGORITHM=<jwt-algorithm>           # e.g. HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=<minutes>
   ```

## 🏃 Running the Application

Start the development server:

```bash
uvicorn main:app --reload
```

Or run directly:

```bash
python main.py
```

The API will be available at `http://127.0.0.1:8000`.
Access the interactive API documentation at:
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

## 🧪 Testing

The project uses **pytest** with a separate SQLite test database (`test_database.db`). Tests cover the three active modules:

```bash
pytest
```

Or use the test runner:

```bash
python tests/run_tests.py
```

| Module | Tests | Coverage |
|--------|:-----:|----------|
| Auth | 8 | Login (username/email), error cases, token validation |
| Users | 15 | Registration, validation (email/password), profile get/update |
| House | 18 | CRUD operations, ownership isolation, error handling |
| **Total** | **41** | |

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

Copyright 2025 PythoneersAssist
