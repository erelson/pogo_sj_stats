#! /usr/bin/env python3

# Age survey module for Flask app

# Standard library
import os
from datetime import datetime

# Third party
from flask import request, flash, redirect, url_for, render_template
import matplotlib
matplotlib.use("svg")
import matplotlib.pyplot as plt
from sqlalchemy.orm import Session

# Local
from tables import AgeSurveyTrainer, AgeSurveyResponse
from settings import PLOT_DIR


def register_age_survey_routes(app, engine):
    """Register age survey routes with the Flask app"""
    
    @app.route('/age-survey', methods=['GET', 'POST'])
    def age_survey():
        session = Session(engine, autoflush=True)
        if request.method == 'POST':
            proper_trainer_name = request.form.get('trainer_name')
            trainer_name = proper_trainer_name.lower()
            plot_trainer_name = proper_trainer_name
            max_storage = request.form.get('max_storage')
            current_pokemon_count = request.form.get('current_pokemon_count')

            # Validate input
            if not max_storage.isdigit() or not current_pokemon_count.isdigit():
                flash('Please provide valid inputs.')
                return redirect(url_for('age_survey'))

            # Retrieve or create trainer
            if not trainer_name:
                plot_trainer_name = None
                proper_trainer_name = "Anonymous"
                trainer_name = "anonymous"
            trainer = session.query(AgeSurveyTrainer).filter_by(name=trainer_name).first()
            if not trainer:
                trainer = AgeSurveyTrainer(name=trainer_name, proper_name=proper_trainer_name)
                session.add(trainer)
                session.commit()

            # Collect age data
            age_data_entries = []
            per_year_sum = 0
            for key, value in request.form.items():
                if key.startswith('year') and value.isdigit():
                    year_str = key[4:]  # Extract year value from the key
                    age_data_entries.append(f'{year_str},{value}')
                    per_year_sum += int(value)

            age_data_str = '\n'.join(age_data_entries)

            # Create and save survey response
            response = AgeSurveyResponse(
                trainer_id=trainer.id,
                timestamp=str(datetime.now().timestamp()),
                max_storage=int(max_storage),
                current_pokemon_count=int(current_pokemon_count),
                age_data=age_data_str
            )
            session.add(response)
            session.commit()
            session.flush()

            flash('Survey submitted successfully!')
            plot_data(int(max_storage), int(current_pokemon_count), age_data_str, plot_trainer_name)
            plotfile = os.path.join(PLOT_DIR, "single_survey_plot.svg")
            with open(plotfile, 'r') as fr:
                svgtext = fr.read()
            return render_template('age_survey.html', datetime=datetime, svgplot=svgtext)

        # For GET request, render the survey form
        return render_template('age_survey.html', datetime=datetime)


def plot_data(max_storage, current_pokemon_count, age_data_str, trainer=None):
    """Generate and save age distribution plot"""
    prev_mons = current_pokemon_count
    mons = []
    data = []
    currdate = datetime.now().date()
    print("uhhh")
    print(age_data_str)
    dates = []
    for line in age_data_str.splitlines():
        a, b = line.split(",")
        delta = int(currdate.year) - int(a)
        dates.append(delta)
        data.append(int(b))
        mons.append(prev_mons)
        prev_mons -= int(b)

    # Create the plot
    fig, axen = plt.subplots(2)
    ax1, ax2 = axen
    ax1.plot(dates, mons, label=f"Pokémon age distribution{' for ' + trainer if trainer else ''}", marker='o')
    ax1.plot(*zip(*[(d, max_storage) for d in dates]), label=None)
    ax1.set_ylabel("Cumulative # of mons\nolder than X years")
    ax1.set_title("Pokémon age distribution")
    ax1.grid(True)
    ax2.plot(dates, data, label="Pokemon age distribution", marker='o')
    ax2.set_xlabel("Age (years)")
    ax2.set_ylabel("# of mons about X\nyears old")
    ax2.grid(True)
    plt.ylim(ymin=0)

    # Save the figure as an SVG file
    plotfile = os.path.join(PLOT_DIR, "single_survey_plot.svg")
    fig.savefig(plotfile, format="svg")

    print(f"SVG plot saved as '{plotfile}'")