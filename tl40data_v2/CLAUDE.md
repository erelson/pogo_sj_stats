# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Restrictions

Claude code agents should NEVER attempt to ssh to the production server.
Claude code agents should NEVER try to run or copy the code within `deploy_code.bash`

## Common Commands

### Local Development

#### Virtual Environment (Recommended)
- Setup virtual environment: `./setup_venv.sh`
- Activate virtual environment: `source venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`
- Run Flask app locally: `./run.sh` (auto-detects venv, serves on http://localhost:5000/survey)
- Initialize static database tables: `./fill_static_tables.py`

#### System Python (Quick Testing)
- Install dependencies: `pip install -r requirements.txt`
- Run Flask app locally: `python3 app.py fakekeytexthere` (serves on http://localhost:5000/survey)
- Initialize static database tables: `./fill_static_tables.py`

### Database Management
- Download latest DB from server: `./grab_latest_db.bash`
- Upload local DB to server: `./push_db.bash` (prompts for confirmation)
- Generate monthly leaderboard HTML: `python3 dashboard_html_from_db.py`

### Stats Configuration Updates
- Update stat limits (monthly): `./parse_and_update_from_godex.site.py` then `./upload_stat_limits.bash`
- Upload stats.json changes: `./upload_stat_limits.bash` (commits changes and uploads)

## Architecture Overview

### Core Components
- **Flask Web App** (`app.py`): Main survey application with WTForms for data collection
- **Database Layer** (`tables.py`): SQLAlchemy models for Trainer, Response, Stat, and AgeSurvey tables
- **Survey Configuration** (`stats.json`): Defines all trackable stats with medal thresholds, limits, and metadata
- **Report Generation** (`dashboard_html_from_db.py`): Creates monthly HTML leaderboards from database

### Data Flow
1. **Survey Collection**: Flask app presents dynamically generated forms based on `stats.json`
2. **Data Storage**: Responses stored in SQLite database with trainer linking
3. **Report Generation**: Python scripts query database to generate monthly HTML leaderboards
4. **Deployment**: Generated HTML files and database are uploaded to remote server

### Key Configuration Files
- `stats.json`: Complete survey field definitions (name, type, medal thresholds, limits, icons)
- `report_fields_1.json`: Subset of stats to include in leaderboard reports
- `settings.py`: Database connection and file path configuration
- `config.toml`: Server login credentials for deployment scripts

### Database Schema
- **Trainer**: User accounts with name normalization
- **Stat**: Survey field definitions (synced from stats.json)
- **Response**: Individual survey submissions with trainer_id and stat values
- **AgeSurveyTrainer/Response**: Separate tables for age-related surveys

### Survey Field Management
Stats in `stats.json` have these key properties:
- `required`: Controls visibility (1=required, 0=optional, -1=hidden)
- `monotonic`: Whether values should only increase over time
- `maximum`: Current known maximum value for the stat
- Medal thresholds: `bronze`, `silver`, `gold`, `platinum` levels

### Deployment Architecture
- Local development with SQLite database
- Remote Apache server with reverse proxy to Flask daemon
- Manual database sync and HTML generation workflow
- Static file serving for icons and generated leaderboards
