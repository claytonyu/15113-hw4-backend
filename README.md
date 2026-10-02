# 15-113 HW4 - Front+Back-end App (Canvas Todo App)

## Overview
This backend acts as a middleman between the front-end display and the Canvas API & Database.

It queries courses and assignments from a user from Canvas, and displays them as tasks to do on the webapp. The user can edit these tasks and create custom tasks, and these are all saved in a Render Postgres Database. The user can also ignore tasks or courses from appearing on the main page.

Also see the [prompt log](PROMPT_LOG.md)!

## Endpoints
Full details (request/response shapes, status codes, error handling) are in [BACKEND_IMPLEMENTATION.md](BACKEND_IMPLEMENTATION.md). Every endpoint below requires `Authorization: Bearer <session_token>` except `POST /auth/token` and `GET /health`.

### Authentication
The user, to use the app, must authenticate with a Canvas PAT token:
- `POST /auth/token` — The user inputs a Canvas PAT to authenticate with the webapp, which returns a session token (login).
- `GET /auth/me` — get the current user information.
- `GET /health` — health check, no auth required.

The user can also disengage with the app in varying levels:

- `POST /auth/logout` — end the current session & token.
- `DELETE /auth/canvas` — disconnect Canvas (deletes stored PAT and sessions, but keeps data).
- `DELETE /auth/account` — delete the user and all of their data.

### Tasks
The main part of the app is to access and update tasks:
- `GET /tasks` — list the user's tasks, optionally filtered by course.
- `POST /tasks` — create one or more tasks.
- `PATCH /tasks` — update one or more tasks.
- `DELETE /tasks` — delete one or more tasks.

### Canvas
Another large part of this project is syncing assignments with Canvas. These are backend endpoints, which get further translated into communications with the Canvas API:
- `POST /canvas/sync` — pull current courses/assignments from Canvas.
- `GET /canvas/courses` — list all known courses.
- `GET /canvas/assignments` — list all known assignments.

Once seen, the user can choose to keep or ignore a course / task from appearing on the main task-tracking page.

- `PATCH /canvas/courses` — keep or ignore courses.
- `PATCH /canvas/assignments` — keep or ignore assignments (keeping creates a task).

## Setup & Running Locally

The backend requires Python 3.14 and a Render Postgres database, with the packages found in the `requirements.txt`.

### Environment Variables Required
- `DATABASE_URL` - the Postgres connection URL provided by Render.
- `ENCRYPTION_KEY` - A Fernet key used to encrypt Canvas PAT tokens. Generated once.
- `FRONTEND_URL` - The frontend's origin, used for CORS.


## Authentication & Secret Handling
- All API keys and secrets live in environment variables, inputted on the Render dashboard.
- Users' Canvas PAT is only submitted once to the token endpoint. Once validated, it is encrypted using Fernet encryption with a secret encryption key and stored in the database. It is only used between backend and Canvas API communication, from then on.
- Users (front-end) are able to authenticate with the session token given, which expires after one week.
- Each user can only access their data.
- Logging out deletes the backend session token, while disconnecting Canvas removes the PAT token from the database.