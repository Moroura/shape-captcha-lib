# Shape CAPTCHA Library

A custom server-side CAPTCHA for Python web applications (with examples for FastAPI). It challenges users to identify one of several geometric shapes in a generated image. This is a fully server-side implementation with no dependencies on third-party CAPTCHA services.

## Key Features

* Generates CAPTCHA images containing multiple (e.g., 10) geometric shapes.
* Each shape in the image has a unique type and a unique color.
* Shapes are randomly placed with varying sizes and orientations (rotations).
* User's response (selected shape) is verified entirely on the server-side.
* Uses Redis for temporary storage of active CAPTCHA challenge states.
* Flexible registration system for easily adding new custom shape types.

## Requirements

* Python 3.9+
* Pillow (for image generation)
* Redis (asyncio-compatible client, e.g., `redis[asyncio]`)

## Installation

**Currently (in development):**

The library can be installed from local sources in editable mode:
```Bash
# From within the shape-captcha-project directory
pip install -e .
```
Or by building a wheel file and then installing it:

```Bash
# In the shape-captcha-project directory
python -m build
pip install dist/shape_captcha_lib-*.whl 
```
In the future (after publishing to PyPI):

```Bash
pip install shape-captcha-lib
```
Quick Start & Usage (FastAPI Example)
Below is a conceptual example of how to integrate the library into your FastAPI application.

1. Initialize CaptchaChallengeService:

The service manages the CAPTCHA logic. It needs to be initialized with a Redis client.

```Python
# In your FastAPI application's main.py
from fastapi import FastAPI, Depends, Request, HTTPException, status
from contextlib import asynccontextmanager
import redis.asyncio as redis_async # Use an alias to avoid conflict if library also uses 'redis'
import os
from typing import Optional # Added for Optional type hint

# Assuming your library is installed and importable
from shape_captcha_lib import CaptchaChallengeService 
# from shape_captcha_lib.config_models import CaptchaDefaultConfig # If you create a config model for the library

# CAPTCHA Redis settings (configured by the library user)
MY_APP_CAPTCHA_REDIS_HOST = os.getenv("MY_APP_CAPTCHA_REDIS_HOST", "localhost")
MY_APP_CAPTCHA_REDIS_PORT = int(os.getenv("MY_APP_CAPTCHA_REDIS_PORT", 6379))
MY_APP_CAPTCHA_REDIS_DB = int(os.getenv("MY_APP_CAPTCHA_REDIS_DB_FOR_CAPTCHA", 2)) # Recommended separate Redis DB

captcha_service_instance: Optional[CaptchaChallengeService] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global captcha_service_instance
    # ... other application resource initializations ...
    
    # Initialize Redis client for CAPTCHA
    captcha_redis = redis_async.Redis(
        host=MY_APP_CAPTCHA_REDIS_HOST,
        port=MY_APP_CAPTCHA_REDIS_PORT,
        db=MY_APP_CAPTCHA_REDIS_DB,
        decode_responses=True 
    )
    try:
        await captcha_redis.ping()
        print(f"Successfully connected to CAPTCHA Redis (DB {CAPTCHA_REDIS_DB})") # Replace with logger
    except Exception as e:
        print(f"Failed to connect to CAPTCHA Redis (DB {CAPTCHA_REDIS_DB}): {e}") # Replace with logger
        captcha_redis = None 

    if captcha_redis:
        captcha_service_instance = CaptchaChallengeService(
            redis_client=captcha_redis 
        )
        app.state.captcha_service = captcha_service_instance 
        print("CaptchaChallengeService initialized and stored in app.state") # Replace with logger
    else:
        app.state.captcha_service = None
        print("CaptchaChallengeService NOT initialized due to Redis connection failure.") # Replace with logger
        
    yield 
    
    if captcha_redis:
        await captcha_redis.close()
        print("CAPTCHA Redis connection closed.") # Replace with logger
    # ... other resource cleanup ...

app = FastAPI(lifespan=lifespan)

# Dependency to get the CAPTCHA service in your endpoints
async def get_captcha_service_dependency(request: Request) -> CaptchaChallengeService:
    service = getattr(request.app.state, 'captcha_service', None)
    if not service:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                 detail="CAPTCHA service not available or not initialized.")
    return service
```
2. Create an API Endpoint to Serve CAPTCHA Challenges:

In your application, create a router and an endpoint that uses the CaptchaChallengeService.

```Python
# In your application, e.g., in a routers/captcha_api_router.py file
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import base64
import io
from typing import Annotated # For Python 3.9+

# Import the dependency and service (paths may vary based on your app structure)
# from ..main import get_captcha_service_dependency # If get_captcha_service_dependency in main.py
# from shape_captcha_lib import CaptchaChallengeService 

# Assuming get_captcha_service_dependency is defined as above
# and you might define a Pydantic response model in your library or here:
class CaptchaChallengePublicResponse(BaseModel):
    captcha_id: str
    image_base64: str # e.g., "data:image/png;base64,..."
    prompt_text: str

captcha_api_router = APIRouter(prefix="/captcha", tags=["CAPTCHA Generation"])

@captcha_api_router.get("/new-challenge", response_model=CaptchaChallengePublicResponse)
async def get_new_captcha_challenge_endpoint(
    captcha_service: Annotated[CaptchaChallengeService, Depends(get_captcha_service_dependency)] 
):
    try:
        captcha_id, image_obj, prompt_text, _ = await captcha_service.create_challenge()
        
        buffered = io.BytesIO()
        image_obj.save(buffered, format="PNG")
        img_str_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        return CaptchaChallengePublicResponse(
            captcha_id=captcha_id,
            image_base64=f"data:image/png;base64,{img_str_base64}",
            prompt_text=prompt_text
        )
    except ConnectionError as e: 
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
                 detail=f"CAPTCHA service error: {e}")
    except ValueError as e: 
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                 detail=f"CAPTCHA generation error: {e}")
    except Exception as e:
        # In a real app, use logger.error(f"Unexpected error in CAPTCHA endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                 detail="Could not generate CAPTCHA.")
```
 Remember to include this router in your main FastAPI application:
```Python
 app.include_router(captcha_api_router, prefix="/api/") // Or your desired API prefix
```
3. Integrate CAPTCHA Verification into a Protected Endpoint (e.g., User Registration):

Your endpoint's request model (e.g., for registration) will need to include fields for captcha_id and the user's CAPTCHA response data (click coordinates).

```Python
# In your router that handles, for example, user registration
from pydantic import BaseModel, Field 
from fastapi import HTTPException, status # Ensure these are imported
# from ..main import get_captcha_service_dependency
# from shape_captcha_lib import CaptchaChallengeService

# Example of extending your registration request model
class YourAppRegistrationForm(BaseModel): # Replace with your actual model name
    username: str
    email: str
    password: str
    # ... other fields for your form ...
    captcha_id: str = Field(..., description="ID of the received CAPTCHA challenge")
    captcha_click_x: int = Field(..., description="X-coordinate of the click on the CAPTCHA image")
    captcha_click_y: int = Field(..., description="Y-coordinate of the click on the CAPTCHA image")

# @your_main_app_router.post("/users/register") // Example endpoint
# async def process_user_registration(
#     form_data: YourAppRegistrationForm,
#     captcha_service: Annotated[CaptchaChallengeService, Depends(get_captcha_service_dependency)]
# ):
#     is_captcha_valid = await captcha_service.verify_solution(
#         captcha_id=form_data.captcha_id,
#         click_x=form_data.captcha_click_x,
#         click_y=form_data.captcha_click_y
#     )
#     if not is_captcha_valid:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST, # Or 422 Unprocessable Entity
#             detail="Invalid CAPTCHA solution or challenge expired."
#         )
    
#     # ... rest of your user registration logic ...
#     return {"message": "User registered successfully"}
```
**How It Works (CAPTCHA Mechanism)**

The client application requests a new CAPTCHA challenge from the API (GET /api/captcha/new-challenge).

The server (using CaptchaChallengeService):
Generates a unique captcha_id.

Creates an image with ~10 different geometric shapes (unique types, colors, random sizes, and positions).

Selects one of the shapes/types as the "target" for the user.

Stores information about the target shape and the parameters of all shapes in the image in Redis with a short time-to-live (TTL).
Returns the captcha_id, the image (as a base64 string), and a prompt (e.g., "Click on the square") to the client.

The client application displays the image and the prompt. The user clicks on a shape. Client-side JavaScript determines the click coordinates (x, y) relative to the image.

When submitting the main form (e.g., registration), the client sends the captcha_id, captcha_click_x, and captcha_click_y along with other data.

The server-side endpoint (e.g., registration):

Calls captcha_service.verify_solution() with the received captcha_id and click coordinates.

The service retrieves the stored challenge data from Redis, verifies if the click falls within the target shape (using precise geometry), and then deletes the entry from Redis.

If verification fails, an error is returned. Otherwise, processing of the main request continues.
Running Tests (for library developers)

To test the shape-captcha-lib library itself:

```Bash
# From the root directory of shape-captcha-project
pytest
```
(Assumes tests for the library are in the shape_captcha_project/tests/ directory.)

License
This project is distributed under the MIT License (or your chosen license). See the LICENSE file for full details.
