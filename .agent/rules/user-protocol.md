# Development Protocol & Best Practices

## Testing

- **DO NOT** run tests locally outside the Docker environment
- Always run tests through the Docker container using `docker-compose exec server pytest` or the justify command
- This ensures test environment consistency and prevents environment-specific issues

## Version Control

- **DO NOT** execute git commands like `git push`, `git commit`, or other version control operations
- The user will handle all git operations manually
- Focus on code changes only; do not manage the repository state

## Architecture & Code Structure

### Three-Layer Architecture Pattern

All code must follow the three-layer structure: **Repository → Service → Router**

#### Layer 1: Repository (Data Access)

- Located in dedicated repository modules
- Direct database queries and ORM interactions
- Example: `UserRepository.get_by_id(user_id)`, `UserRepository.create(user_data)`

#### Layer 2: Service (Business Logic)

- Located in `service.py`
- Contains business logic, validation, and data transformation
- Depends on Repository layer
- Example: `UserService.authenticate(email, password)`, `UserService.register(user_data)`

#### Layer 3: Router (API Endpoints)

- Located in `router.py`
- HTTP request/response handling only
- Depends on Service layer
- Example: `@router.post("/login")`, `@router.get("/users/{user_id}")`

### Key Principles

- **Never** put business logic in routes
- **Never** put database queries in services
- **Never** put HTTP logic in repositories or services
- Keep dependencies flowing downward: Router → Service → Repository
- Each layer has a single responsibility

## File Organization

- Route handlers and dependencies stay in `router.py`
- Business logic goes in `service.py`
- Data models and queries go in `models.py`
- Schema validation stays in `schemas.py`
