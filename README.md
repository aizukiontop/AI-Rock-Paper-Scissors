# AI Rock Paper Scissors --- Robot Arena

AI Rock Paper Scissors is an interactive web-based game that combines
the classic Rock Paper Scissors experience with real-time hand gesture
recognition and an AI-powered robot opponent.

Built with React, TypeScript, and Flask, the application allows players
to compete against a robot using their actual hand gestures through a
webcam. The project also features an interactive game arena and a
leaderboard for displaying player scores.

**Live Demo:** https://ai-rock-paper-scissors.fly.dev/

**GitHub Repository:**
https://github.com/aizukiontop/AI-Rock-Paper-Scissors

## Features

-   **Real-Time Hand Gesture Recognition** --- Use your webcam to detect
    and recognize Rock, Paper, and Scissors hand gestures.
-   **AI Robot Opponent** --- Play against an automated robot opponent
    that responds to the player's moves.
-   **Interactive Game Arena** --- Experience Rock Paper Scissors
    through an interactive browser-based gaming interface.
-   **Camera-Based Gameplay** --- Control the game using physical hand
    gestures instead of relying entirely on keyboard or mouse input.
-   **Leaderboard** --- Display player scores and competitive rankings.
-   **Game Session Management** --- Handle player information, game
    sessions, and match-related data through the backend.
-   **Backend API Integration** --- Connect the React frontend to Flask
    endpoints for game functionality and data processing.
-   **Responsive Interface** --- Access the application through
    different screen sizes and modern web browsers.
-   **Browser-Based Experience** --- Play directly through a web browser
    without installing a separate desktop application.

## Built With

-   **React** --- Frontend library for building the user interface.
-   **TypeScript** --- Static typing for more maintainable and reliable
    frontend code.
-   **Vite** --- Frontend development server and build tool.
-   **Python** --- Backend programming language.
-   **Flask** --- Backend framework for application routes and API
    endpoints.
-   **MediaPipe Tasks Vision** --- Hand landmark detection and gesture
    recognition.
-   **Tailwind CSS** --- Utility-first CSS framework for interface
    styling.
-   **Gunicorn** --- Production WSGI server for running the Flask
    application.
-   **Docker** --- Containerization for application deployment.
-   **Fly.io** --- Application hosting and deployment platform.

## How It Works

### Player Experience

1.  Open the application through a web browser.
2.  Allow camera access when prompted.
3.  Position your hand in front of the webcam.
4.  Perform a Rock, Paper, or Scissors gesture.
5.  The application detects the hand gesture and processes the player's
    move.
6.  The robot opponent responds with its move.
7.  View the match result and corresponding score.

### Hand Gesture Recognition

The application uses MediaPipe Tasks Vision to process webcam input and
detect hand landmarks.

The detected hand landmarks are used by the frontend gesture recognition
logic to identify the player's hand gesture.

The recognized move is then processed by the application and used during
gameplay.

### Backend Processing

The Flask backend handles application routes, API requests, and
game-related functionality.

The React frontend communicates with the backend through API endpoints,
allowing the game interface and server-side functionality to work
together.

## Getting Started

### Prerequisites

Before running the project locally, make sure you have the following
installed:

-   [Python](https://www.python.org/)
-   [Node.js](https://nodejs.org/)
-   npm (included with Node.js)
-   [Git](https://git-scm.com/)

### Installation

**1. Clone the repository**

``` bash
git clone https://github.com/aizukiontop/AI-Rock-Paper-Scissors.git
```

**2. Open the project folder**

``` bash
cd AI-Rock-Paper-Scissors
```

**3. Install Python dependencies**

``` bash
pip install -r requirements.txt
```

**4. Navigate to the frontend directory**

``` bash
cd frontend
```

**5. Install frontend dependencies**

``` bash
npm install
```

**6. Build the frontend**

``` bash
npm run build
```

The production frontend build is generated in the `static/app` directory
for Flask to serve.

**7. Return to the project root**

``` bash
cd ..
```

**8. Start the Flask application**

``` bash
python main.py
```

**9. Open the application**

Visit the following address in your browser:

``` text
http://localhost:5000
```

> Note: Webcam access requires a secure context. Use `localhost` for
> local development or HTTPS when accessing the deployed application.

## Project Structure

The project is organized into a React and TypeScript frontend, a Flask
backend, static frontend assets, and deployment configuration files.

``` text
AI-Rock-Paper-Scissors/
│
├── frontend/              # React and TypeScript application
│   ├── src/               # Frontend source code
│   ├── public/             # Public frontend assets
│   └── package.json        # Frontend dependencies and scripts
│
├── src/                    # Flask backend application
│   ├── app.py              # Flask application factory
│   └── routes.py           # Application routes and API endpoints
│
├── static/
│   └── app/                # Compiled frontend assets
│
├── templates/              # Flask HTML templates
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker build configuration
├── fly.toml                # Fly.io deployment configuration
├── Procfile                # Production process configuration
├── .dockerignore           # Docker build exclusions
└── README.md
```

> The structure above provides an overview of the main project
> directories and files. Additional files and subdirectories may exist
> in the repository.

## Deployment

The application is deployed using **Fly.io**.

Docker is used to prepare the application for production deployment.

The deployment process includes:

1.  Installing frontend dependencies.
2.  Building the React application using Vite.
3.  Installing Python backend dependencies.
4.  Configuring Gunicorn to serve the Flask application.
5.  Packaging the application using Docker.
6.  Deploying the container to Fly.io.

The application is accessible through HTTPS:

https://ai-rock-paper-scissors.fly.dev/

## Project Objective

AI Rock Paper Scissors was developed as an interactive full-stack web
development project to explore the integration of frontend development,
backend programming, and computer vision.

The project demonstrates how real-time webcam input and hand gesture
recognition can be incorporated into a browser-based gaming application.

It also provides practical experience in building API-driven
applications, integrating third-party computer vision tools, managing
application state, and deploying a full-stack project to a cloud hosting
platform.

## Author

**Marion Anthony S. Dingal**\
Computer Science Student

-   **Portfolio:** https://mariondingal.vercel.app/
-   **GitHub:** https://github.com/aizukiontop

## Live Demo

Visit the deployed application:

https://ai-rock-paper-scissors.fly.dev/

## Disclaimer

AI Rock Paper Scissors is a student-developed project for educational
and demonstration purposes. Webcam-based gesture recognition depends on
camera availability, lighting conditions, and hand visibility. The
application is not intended to provide professional computer vision or
AI benchmarking results.
