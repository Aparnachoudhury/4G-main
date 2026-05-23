# iWOWN Health Monitoring FastAPI API

A production-ready FastAPI application for iWOWN health monitoring devices, built with security, scalability, and maintainability in mind. This application provides a robust backend for health monitoring devices with secure MongoDB integration and comprehensive API endpoints.

## Features

- **Production-Ready**: Built with FastAPI for high performance and automatic API documentation
- **iWOWN Compatible**: Implements all 6 required iWOWN endpoints with exact path matching
- **Async Processing**: Background task processing for health data
- **Comprehensive Logging**: Structured logging with configurable levels
- **Docker Support**: Containerized deployment with Docker and Docker Compose
- **MongoDB Integration**: Full MongoDB Atlas integration with secure connection handling
- **Security**: Environment-based configuration, no hardcoded credentials
- **Monitoring**: Health check endpoints, container health checks, and metrics
- **Graceful Degradation**: API starts even if database is unavailable

## iWOWN Endpoints

The API implements the exact endpoints required by iWOWN devices:

- `POST /4g/pb/upload` - Health data upload
- `POST /4g/alarm/upload` - Alarm data upload  
- `POST /4g/call_log/upload` - Call log/SOS upload
- `POST /4g/deviceinfo/upload` - Device information upload
- `POST /4g/status/notify` - Status notifications
- `POST /4g/health/sleep` - Sleep health data

## Dashboard API Endpoints

- `GET /health` - Health check
- `GET /api/devices` - List all devices
- `GET /api/stats` - System statistics
- `GET /api/device/{device_id}/health` - Device health data
- `GET /api/device/{device_id}/alarms` - Device alarms
- `GET /api/device/{device_id}/sos` - Device SOS data

## Quick Start

### Prerequisites

1. **Python 3.11+** installed
2. **MongoDB Atlas** account and cluster
3. **Docker** (optional, for containerized deployment)

### Environment Setup

1. **Create `.env` file** in the project root:
   ```bash
   # MongoDB Configuration (Required)
   MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
   MONGODB_DATABASE=iwown_health
   ```

2. **Replace credentials** with your actual MongoDB Atlas connection string

### Local Development

1. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python main.py
   ```

4. **Access the API:**
   - API: http://localhost:8000
   - Interactive docs: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

### Docker Deployment

1. **Build and run with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

2. **Access the API:**
   - API: http://localhost:8000
   - Interactive docs: http://localhost:8000/docs

**Note:** Docker automatically reads from `.env` file for environment variables.

### Production Deployment

1. **Set environment variables** in your production environment:
   ```bash
   export MONGODB_URL="mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority"
   export MONGODB_DATABASE="iwown_health"
   ```

2. **Run with production settings:**
   ```bash
   python main.py
   ```

3. **Or use Docker Compose:**
   ```bash
   docker-compose -f docker-compose.yml up -d
   ```

## Configuration

The application uses environment variables for configuration. **Only essential variables are required**:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MONGODB_URL` | ✅ **Yes** | - | MongoDB Atlas connection string |
| `MONGODB_DATABASE` | ❌ No | `iwown_health` | MongoDB database name |

### Environment File Setup

Create a `.env` file in your project root:

```bash
# MongoDB Configuration (Required)
MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=iwown_health
```

**Security Note:** Never commit `.env` files to version control. The `.gitignore` file already excludes them.

## Project Structure

```
4G/
├── main.py                 # Main FastAPI application
├── config.py               # Configuration settings (environment-based)
├── database.py             # MongoDB connection and database operations
├── requirements.txt        # Python dependencies
├── Dockerfile             # Docker container definition (production-ready)
├── docker-compose.yml     # Docker Compose configuration
├── .dockerignore          # Docker build exclusions
├── .gitignore             # Git exclusions
├── README.md              # This file
├── CODE_INDEX.md          # Comprehensive codebase documentation
├── .env                   # Environment variables (create this file)
└── logs/                  # Application logs (created at runtime)
```

## API Documentation

Once the application is running, visit:
- **Interactive API docs**: http://localhost:8000/docs
- **ReDoc documentation**: http://localhost:8000/redoc
- **OpenAPI schema**: http://localhost:8000/openapi.json

## Testing

### Manual Testing

Test the iWOWN endpoints with curl:

```bash
# Health data upload
curl -X POST "http://localhost:8000/4g/pb/upload" \
  -H "DeviceId: test-device-123" \
  -d "test-data"

# Device info upload
curl -X POST "http://localhost:8000/4g/deviceinfo/upload" \
  -H "DeviceId: test-device-123" \
  -H "Content-Type: application/json" \
  -d '{"battery": 85, "firmware_version": "1.2.3"}'

# Get devices list
curl "http://localhost:8000/api/devices"

# Health check
curl "http://localhost:8000/health"
```

### Docker Testing

Test with Docker containers:

```bash
# Build and start services
docker-compose up -d

# Check service health
docker-compose ps

# View logs
docker-compose logs -f iwown-api

# Test health endpoint
curl "http://localhost:8000/health"
```

## Production Considerations

### Security
- ✅ **No hardcoded credentials** - All secrets in environment variables
- ✅ **Secure MongoDB connection** - SSL/TLS enabled by default
- ✅ **Container security** - Non-root user, minimal attack surface
- ✅ **Environment isolation** - Separate configs for dev/staging/prod
- 🔒 **Additional recommendations:**
  - Use HTTPS in production
  - Implement rate limiting
  - Add authentication if required
  - Configure CORS origins appropriately

### Performance
- ✅ **MongoDB Atlas** - Automatic scaling and optimization
- ✅ **Connection pooling** - Optimized database connections
- ✅ **Async processing** - FastAPI async support
- ✅ **Container optimization** - Multi-stage builds, minimal images

### Monitoring
- ✅ **Health check endpoints** - `/health` for API status
- ✅ **Container health checks** - Docker health monitoring
- ✅ **Structured logging** - Configurable log levels
- ✅ **Graceful degradation** - API works without database

### Scaling
- ✅ **Horizontal scaling** - Multiple container instances
- ✅ **MongoDB Atlas scaling** - Automatic cluster scaling
- ✅ **Load balancing** - Nginx reverse proxy included
- ✅ **Container orchestration** - Docker Compose ready

## Migration from Flask Demo

This FastAPI application is a direct replacement for the Flask demo in the Jupyter notebook:

| Flask Demo | FastAPI Production |
|------------|-------------------|
| Flask server | FastAPI with Uvicorn |
| ngrok tunneling | Direct deployment |
| In-memory storage | MongoDB Atlas integration |
| Basic error handling | Comprehensive error handling |
| No validation | Pydantic validation |
| No async support | Full async support |
| No documentation | Auto-generated OpenAPI docs |
| Hardcoded credentials | Environment-based configuration |
| No containerization | Docker + Docker Compose |
| No health checks | Built-in health monitoring |

## Support

For issues and questions:
1. **Check the API documentation** at `/docs` when the server is running
2. **Review the logs** in the `logs/` directory
3. **Check the configuration** in `config.py`
4. **Verify environment variables** in your `.env` file
5. **Check Docker logs** if using containers: `docker-compose logs -f`

## Troubleshooting

### Common Issues

1. **MongoDB Connection Failed:**
   - Verify your `.env` file has correct `MONGODB_URL`
   - Check network connectivity to MongoDB Atlas
   - Verify MongoDB Atlas cluster is running

2. **API Won't Start:**
   - Ensure `.env` file exists and has required variables
   - Check Python version (3.11+ required)
   - Verify all dependencies are installed

3. **Docker Issues:**
   - Ensure `.env` file exists before running `docker-compose up`
   - Check Docker and Docker Compose versions
   - Verify ports 8000, 80, 443 are available

### Getting Help

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Logs**: Check `logs/` directory or Docker logs
- **Configuration**: Review `config.py` and `.env` file

## Recent Updates & Improvements

### Security Enhancements
- ✅ **Removed all hardcoded credentials** from source code
- ✅ **Environment-based configuration** using `.env` files
- ✅ **Secure Docker setup** with non-root users and health checks
- ✅ **MongoDB SSL/TLS** connection handling

### Code Quality
- ✅ **Simplified configuration** - Only essential variables required
- ✅ **Graceful error handling** - API starts even without database
- ✅ **Comprehensive logging** - Better debugging and monitoring
- ✅ **Clean project structure** - Removed unnecessary files

### Docker Improvements
- ✅ **Production-ready Dockerfile** with security best practices
- ✅ **Health checks** for both containers and applications
- ✅ **Optimized builds** with `.dockerignore` file
- ✅ **Environment variable support** in Docker Compose

### Documentation
- ✅ **Updated README** with current setup instructions
- ✅ **CODE_INDEX.md** for comprehensive codebase overview
- ✅ **Troubleshooting guide** for common issues
- ✅ **Security best practices** documentation

## License

This project is part of the iWOWN health monitoring system.
