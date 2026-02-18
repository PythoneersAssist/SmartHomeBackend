# SmartHomeBackend

A modular and scalable backend for Smart Home systems built with FastAPI. This project provides a robust API to manage users, devices, rooms, energy consumption, and automations.

## 🚀 Features

- **Authentication**: Secure user access and authentication flows.
- **User Management**: Manage user profiles and their associated device ecosystems.
- **Device Management**: Comprehensive CRUD operations for registering and controlling smart devices.
- **Room Organization**: Modular organization of devices into rooms and households.
- **Energy Monitoring**: Granular tracking of energy usage at device, room, and household levels.
- **Automations**: Infrastructure for defining and executing smart home automation routines.
- **Notifications**: System-wide notification and communication service.

## 🛠️ Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **ORM**: [SQLAlchemy](https://www.sqlalchemy.org/)
- **Validation**: [Pydantic](https://docs.pydantic.dev/)
- **Server**: [Uvicorn](https://www.uvicorn.org/)

## 📂 Project Structure

```text
├── auth/           # Authentication endpoints and logic
├── automations/    # Automation routine management
├── database/       # SQLAlchemy models and database configuration
├── devices/        # Device registration and control
├── energy/         # Energy usage tracking and analytics
├── notifications/  # Notification services
├── rooms/          # Room and household organization
├── users/          # User management and device associations
├── main.py         # Application entry point
└── README.md       # Project documentation
```

## ⚙️ Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd smarthome-backend
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install fastapi uvicorn sqlalchemy pydantic python-dotenv
   ```

4. **Environment Configuration**:
   Create a `.env` file in the root directory and add your configuration (Database URL, Secret Keys, etc.).

## 🏃 Running the Application

Start the development server using Uvicorn:

```bash
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`. 
You can access the interactive API documentation at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
