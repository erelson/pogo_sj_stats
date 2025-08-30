#! /usr/bin/env python

# Flask!

# Standard library
import argparse
import json
import sys
from datetime import datetime

# Third party
from flask import request, flash, redirect, url_for, send_from_directory, jsonify
from flask import Flask
from flask import render_template
from wtforms import Form, BooleanField, DecimalField, StringField, IntegerField, \
                    PasswordField, validators
from flask_wtf import FlaskForm
import matplotlib
matplotlib.use("svg")  # Set the backend to SVG
import matplotlib.pyplot as plt
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import OperationalError
from sqlalchemy import create_engine
from sqlalchemy.engine import ExceptionContext

# Local
from tables import Stat, Response, Trainer
from tables import AgeSurveyTrainer, AgeSurveyResponse
from settings import LOCAL_DB_SPECIFIER, PLOT_DIR


MEDALS = ["No medal", "Bronze", "Silver", "Gold", "Platinum"]
TYPE_MEDALS = ["Schoolkid",  # This list's fields get put at the very end of the survey
               "Black Belt",
               "Bird Keeper",
               "Punk Girl",
               "Ruin Maniac",
               "Hiker",
               "Bug Catcher",
               "Hex Maniac",
               "Rail Staff",
               "Kindler",
               "Swimmer",
               "Gardener",
               "Rocker",
               "Psychic",
               "Skier",
               "Dragon Tamer",
               "Delinquent",
               "Fairy Tale Girl",
              ]

app = Flask(__name__)


def get_survey_data_in_survey_order(session, user=None):
    """Load data from DB for user and put it in order that we want to display the survey in.

    Args:
        session: sqlalchemy session
        user (str): trainer name
        stats: Preloaded information about stat categories and badge thresholds.
            Otherwise query DB for this information

    Returns:
        stats_list: (TODO rename?) list of lists. Each sublist is
            [Name, img, previous value/None, maximum/None]
    """
    # We get two lists, the stats_list from json
    # and the trainer_data from the database.
    # We want to return the stats in the best order for the person taking the survey...
    # So approach to sorting...
    # - Option 1: Starting from the default offsets, increment the offsets based on the
    # trainer's medal level (since this is what the game uses for ordering)
    # - Option 2: Go stat by stat and bin them into 0/bronze/silver/gold/platinum categories,
    # then concatenate the categories.

    # We ultimately return stat_lists, a list of lists, where each sublist is [Stat, previous_val]

    # If we do not have trainer data, we just return the default order from json.
    # If we have trainer data, we also fill in the previous recorded value.

    stats_list = []  # list of lists, each sublist is [index, Stat, previous_val]; previous_val gets set later
    # For now, load from json. The json is a list in a hand-chosen desired order.
    # This means we can update the order (in the json file), without updating/migrating the database.
    static_stat_info = json.load(open("stats.json", 'r'))  # dict
    stat_keys = static_stat_info["key"]  # list
    stat_vals = static_stat_info["data"]  # dict keyed by Stat Names
    for cnt, stat_name in enumerate(stat_vals):
        stats_list.append([cnt,  # index to sort by later
                           Stat(name=stat_name,
                                **dict(zip(stat_keys, stat_vals[stat_name]))),
                           0,  # previous value
                           ])

    # Get trainer's last survey data if any, to help set order, limits and hints on the survey page.
    trainer = None
    trainer_data = {}
    if user:
        try:
            trainer = session.query(Trainer).filter_by(name=user.lower()).one()
        except NoResultFound:
            # The user doesn't have a submission yet, so blank data.
            pass
    if trainer:
        # trainer_data will be a dict by stat name of values from previous response
        # stderr is used ... why?
        trainer_data = trainer.get_newest_response(session)  # May be None for newly (manually?) added trainer
        if trainer_data is None:
            print(f"Got NO data for trainer {user}..", file=sys.stderr)
            # NOTE this probably shouldn't happen and doesn't happen... so TODO should be an exception
        else:
            print(f"Got trainer {user} data.. non-None? {trainer_data != None}", file=sys.stderr)

    # Calculate offsets for each stat category
    # For each stat category, iterate through its badge amounts, calculating offsets based on previous stat amount.
    # Use cnt as index in stats_list, generated from stats_vals.
    for cnt, key in enumerate(stat_vals):  # iterate through the entries loaded from json
        # Note: key is e.g. "Unique Species Caught"
        x = stat_vals[key]
        statname = x[7]
        try:
            # The keys for trainer_data are actually tuples...  # TODO 1-2025: reading code, this claim seems wrong
            previousval = trainer_data[(key,)]
            if previousval == '':  # Trying to load a new field that is not in the previous response's strdata
                previousval = 0
            else:
                previousval = int(previousval) # TODO int or float support
        except ValueError as e:
            previousval = float(trainer_data[(key,)])  # Technically we could do this always
        except KeyError:
            print("Missing key:", key)  # Stat/key is not in DB; but should be added by next survey submission.
            previousval = 0
        except TypeError:
            #print(f"TypeError with trainer_data[{key}], {type(key)}")
            previousval = 0

        # Calculate order offsets used for ordering of survey items
        bronze_thresh = x[1]
        if bronze_thresh == 0:  # 0 indicates NO MEDALS for this stat
            # Always put these medal-less stats at top of render order
            order_offset = 0
            medal_name = ""
        else:  # All other categories; lower orders for higher badge numbers, displayed first
            # TODO(enhancement): If a state is zero, set the order_offset even higher...
            order_offset = 400
            medal_idx = 1  # 1/2/3/4/5 none/bronze/silver/gold/platinum
            while medal_idx < 5 and previousval >= x[medal_idx]:
                order_offset -= 100
                medal_idx += 1
            medal_name = f"({MEDALS[medal_idx-1]})"

            # Special cases
            if key == "Vivillon Collector":
                order_offset = 499  # hardcode this one to be last before type medals
            elif key in TYPE_MEDALS:
                # Put these after the other medals
                order_offset += 600

        # From CSS stuff, for reference...
        #print(f"    #main-panel .mdl-grid > #{x[4]} " + "{ order: " + f"{order}; " + "}")
        stats_list[cnt][0] += order_offset
        if medal_name:
            stats_list[cnt][2] = f"{previousval} {medal_name}"
        else:
            stats_list[cnt][2] = f"{previousval}"

    # Sort things!
    stats_list.sort(key=lambda x: x[0])

    # Returns:
    # stats: (TODO rename?) list of lists. Each sublist is
    #     [Name, img, previous value/None, maximum/None]
    return stats_list


def print_incomplete_warning():
    # Return text (HTML) that will be displayed above the Submit button
    return "<p><b>There are one or more empty required fields, or errors to correct.</b>"

class RegistrationForm(Form):
    username = StringField('Username', [validators.Length(min=4, max=25)])
    age = IntegerField('Age', [validators.NumberRange(min=4, max=25)])
    email = StringField('Email Address', [validators.Length(min=6, max=35)])
    password = PasswordField('New Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords must match')
    ])
    confirm = PasswordField('Repeat Password')
    accept_tos = BooleanField('I accept the TOS', [validators.DataRequired()])


def load_stats():
    return []

class PogoStatsForm(Form):
    """Form class used for the survey fields. See survey_gen()."""
    pass


def survey_gen(stats_list, formclass, _test_default_val=None):
    """Sets survey fields as attrs on form object

    Also inserts sectional breaks.

    Stats with "required = -1" are not not included in the form (survey).

    Args:
        stats_list: list of Stat objects. Each list will drive a input field on the form.
            The order of the list determines the order of the fields on the form.
        formclass: Class of a form object.
        _test_default_val: Default value for all fields. Normally set by
            test code.

    Returns:
        A formclass with attributes set, ready to be instantiated.
    """
    statlist = []  # lookup of attribute names on the FormClass which hold Field objects
    statdivider = []  # list of booleans: when True, jinja2 template script will add a divider after the stat
    # TODO(enhancement) this is stupidly brittle? Every time I add a new non-badge stat...? or if we get too many badges
    # See also shenanigans around line 150 above.
    sections = [20, 100, 200, 300, 400, 500, 600, 700, 800, 900, 10000]
    section_idx = 0
    for order, stat, previous_val_str in stats_list:  # in order already
        # required == -1 stats are no longer collected
        if stat.required == -1:
            continue
        # Strings are "123 (badge level)" so need to strip second part before casting
        # This previous_val_str to previous_val crap would be good to clean up.
        if stat.numtype == "Float":
            previous_val = float(previous_val_str.split()[0])
        else:
            previous_val = int(previous_val_str.split()[0])
        #print(section_idx, order, stat.icon)
        if order > sections[section_idx]:
            statdivider.append(True)
            while order > sections[section_idx]:
                section_idx += 1
        else:
            statdivider.append(False)

        #print(stat.name, previous_val_str)
        if stat.name == 'Trainer Level':
            minimum = max(40, previous_val)
        elif stat.monotonic:
            try:
                minimum = previous_val  # todo floats
            except:
                minimum = 0
        else:
            minimum = 0
        checks = [validators.NumberRange(min=minimum,
                                         max=stat.maximum if stat.maximum > 0 else None)
                     ]
        default_val = _test_default_val
        if previous_val == stat.maximum:  # Note there are no stats with maximums that are also float values.
            # Fill in the field for already-maxed stats.
            default_val = previous_val
        elif stat.required == 0:
            checks = [validators.Optional()] + checks
        if stat.numtype == "Float":
            # TODO fix float input here?
            # Per wtforms docs, DecimalField is usually preferred over FloatField
            print("FLOAT BOX:", stat.name)
            field = DecimalField(stat.name, validators=checks,
                                 default=default_val,
                                 render_kw={"inputmode": "numeric", "type": "number",
                                            "placeholder": previous_val_str,
                                            "previous_val_with_badge": previous_val_str,  # unused
                                            },
                                 )
        else:
            field = IntegerField(stat.name, validators=checks,
                                 default=default_val, # Could use this but it fills a valid value. Use render_kw["placeholder"] instead
                                 render_kw={"inputmode": "numeric", "type": "number",
                                            "placeholder": previous_val_str,
                                            "previous_val_with_badge": previous_val_str,  # unused
                                            },
                                 )
        # Set the field object on our form, which will later generate the HTML
        # We cast str on stat.icon, otherwise we actually have a sqlalchemy object, and this causes
        # thread issues with sqlite at render time.  (This theory didn't prove correct)
        setattr(formclass, str(stat.icon), field)  # using icon because name has spaces in it
        # Order of newly added attrs is preserved in statlist
        statlist.append(stat.icon)

    setattr(formclass, "statlist", statlist)
    setattr(formclass, "statdivider", statdivider)
    # https://gaming.stackexchange.com/a/281007
    trainername = StringField('Trainer Name',
                              validators=[validators.Length(min=4, max=15),
                                          validators.Regexp(regex=r"^[\w\d]+$",
                                                            message="Trainer name can only be letters and numbers"),
                                  ])
    formclass.trainername = trainername
    #print(type(formclass.statlist), formclass.statlist)
    #setattr(form,
    #form = formclass()
    #return form #formclass()
    return formclass


@app.template_filter()
def printx(*args):
    print("HHHHHHHHHHHHHHHHHHHHHHHHHHHHHHH")
    print(*args)
    return ''

@app.route("/<month>")
def stats_previous(month=None):
    """month is something like 2022-3"""
    # Should load the previous month's stats
    return send_from_directory('static', month)

# Not sure this is necessary
@app.route("/static/<month>")
def stats_previous_from_static(month=None):
    """month is something like 2022-3"""
    # Should load the previous month's stats
    # Historically used this one... but noticed it started concatenating like static/static/x in May 2023
    #return send_from_directory('static', month)
    # Trying to avoid concatenation:
    # Note 10-13-2023: this might not be working? Missing static/scroll2.js...
    #return send_from_directory('/static', month)
    # 10-13-2023: Trying this again:
    return send_from_directory('static', month)
    #  this might work better?
    # Nope
    #return redirect(f"/{month}")
    # Nope
    #return redirect(url_for('stats_previous_from_static', month))


@app.route("/")
def stats():
    return send_from_directory('static', 'index.html')


# TODO not implemented
@app.route('/register', methods=['GET', 'POST'])
def register():
    print()
    print("DEBUG")
    form = RegistrationForm(request.form)
    #print(type(form.username), form.username)
    print(dir(request))
    if hasattr(request, "data"):
        print(request.data)
    if hasattr(request, "values"):
        print(request.values)
    if request.method == 'POST' and form.validate():
        #user = User(form.username.data, form.email.data,
        #            form.password.data)
        #db_session.add(user)
        print(form)
        print(dir(form))
        print("skipped db_session.add call")
        flash('Thanks for registering')

        return redirect(url_for('login'))
    return render_template('register.html', form=form,
                           zip=zip, type=type, print=print,
                           )

@app.route('/survey/<username>', methods=['GET', 'POST'])
def fill_survey_for_user(username=None):
    # TODO sanitize the username string? Check: What does the decorator do already?
    return fill_survey(username)

@app.route('/survey', methods=['GET', 'POST'])
@app.route('/survey/', methods=['GET', 'POST'])
def fill_survey(user=None):
    # Generate a stats list, either default order, or order by user's badge levels if known
    session = Session(engine, autoflush=True)
    stats_list = get_survey_data_in_survey_order(session=session, user=user)

    PogoForm = survey_gen(stats_list, PogoStatsForm)
    try:
        form = PogoForm(request.form)
        real_function_call = True  # TODO cleanup
        # These are debug stuff...
        print("")
        if hasattr(request, "values"):
            print(request.values)
    except RuntimeError:  # likely "Working outside of request context"
        # Presumably this is because we're testing stuff and request isn't defined.
        form = PogoForm()
        real_function_call = False  # TODO cleanup

    # Prefill trainername field
    if user:
        form.trainername.data = user

    html_out = "placeholder"
    print("", file=sys.stderr)
    try:
        print("SUBMISSION HERE - got request type", request.method)
        if hasattr(request, "values"):
            print("Survey values given were:", request.values)
        request_method = request.method
        form_validated = form.validate()
    except RuntimeError:
        # e.g. app.py was run with --test-get-survey-data or similar option
        request_method = 'POST'
        form_validated = True
    # POST via Submit button on survey with validation passing
    if request_method == 'POST' and form_validated:
        # If valid
            # Display validation success
            # Save in DB
            # Display save success
            # Redirect to user history page
        if session:  # is set up
            response = Response.save_response(session, response_values=request.values)
            print(response)
            session.commit()
            session.flush()

            # Submission page
            # <pre> tags preserve the tab characters, so users can paste data into spreadsheets
            html_out = "Thanks for the submission! Stats will be regenerated on the 1st.<p>" \
                    "Here's the raw data you submitted if you want to back it up for your own use:<p>" \
                    "<pre>" \
                    + "<br>".join([f"{k}:\t{v}" for k, v in request.values.items()]) \
                    + "</pre>"
        else:
            print("skipped db_session.add call")
        # TODO subsequent HTML or redirect

    else:
        #print("DEBUG HERE - got", request.method)
        print("RENDER HERE:")

        # Print a helpful warning if there are errors in the survey (i.e. validation failed)
        # otherwise, no-op.
        if request_method == 'POST' and not form_validated:
            print(form_validated)
            print(type(form_validated))
            print("THERE WERE INCOMPLETE STATS:")
            piw = print_incomplete_warning
        else:
            piw = lambda: ""

        try:
            html_out = render_template('survey_template.html', form=form,
                                       zip=zip, type=type, print=print,
                                       print_incomplete_warning=piw,
                                       )
        except RuntimeError:
            pass

    try:
        session.close()
    except:
        pass

    return html_out


@app.route('/visualization')
def trainer_visualization():
    """Display the trainer visualization page"""
    session = Session(engine, autoflush=True)
    try:
        # Get all trainers
        trainers = session.query(Trainer.name).distinct().order_by(Trainer.name).all()
        trainer_names = [t.name for t in trainers]

        # Load stats from JSON and extract categories
        with open('stats.json', 'r') as f:
            stats_data = json.load(f)

        # Parse stats with categories
        stats = []
        categories = set()
        for stat_name, stat_info in stats_data['data'].items():
            # Get category (last item in the array)
            if len(stat_info) >= 10:  # has category field
                category = stat_info[9]
            else:
                category = "General"  # fallback

            categories.add(category)
            stats.append({
                'name': stat_name,
                'icon': stat_info[8],  # icon field
                'category': category
            })

        return render_template('trainer_visualization.html',
                             trainers=trainer_names,
                             stats=stats,
                             categories=sorted(categories))
    finally:
        session.close()


@app.route('/api/trainer-stats', methods=['POST'])
def get_trainer_stats():
    """API endpoint to fetch trainer statistics data"""
    session = Session(engine, autoflush=True)
    try:
        data = request.get_json()
        trainer_name = data['trainer_name']
        stat_names = data['stat_names']
        start_date = data['start_date']
        end_date = data['end_date']
        view_type = data.get('view_type', 'absolute')

        # Find the trainer
        try:
            trainer = session.query(Trainer).filter_by(name=trainer_name.lower()).one()
        except NoResultFound:
            return jsonify({'error': 'Trainer not found'}), 404

        # Convert date strings to timestamps for comparison
        start_timestamp = datetime.strptime(start_date, '%Y-%m-%d').timestamp()
        end_timestamp = datetime.strptime(end_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S').timestamp()

        # Get all responses for this trainer in the date range
        responses = session.query(Response).filter(
            Response.trainer_id == trainer.id,
            Response.timestamp >= str(start_timestamp),
            Response.timestamp <= str(end_timestamp)
        ).order_by(Response.timestamp).all()

        if not responses:
            return jsonify({'error': 'No data found for the selected date range'}), 404

        if len(responses) < 2 and view_type in ['increments', 'rate']:
            return jsonify({'error': 'At least 2 data points required for incremental/rate views'}), 400

        # Get stat names in database order to parse strdata
        stat_names_ordered = [s[0] for s in session.query(Stat.name).order_by(Stat.order_idx).all()]

        # Group responses by month and extract requested stats
        monthly_data = {}

        for response in responses:
            # Convert timestamp to datetime and extract year-month
            response_dt = datetime.fromtimestamp(float(response.timestamp))
            month_key = response_dt.strftime('%Y-%m')

            # Parse strdata to get individual stat values
            stat_values = response.strdata.split(';')
            stat_dict = dict(zip(stat_names_ordered, stat_values))

            # Store the latest response for each month (in case multiple submissions per month)
            if month_key not in monthly_data or response.timestamp > monthly_data[month_key]['timestamp']:
                monthly_data[month_key] = {
                    'timestamp': response.timestamp,
                    'stats': stat_dict
                }

        # Build results for each requested stat
        results = []
        for stat_name in stat_names:
            if stat_name not in stat_names_ordered:
                continue

            data_points = []
            prev_value = None

            # Sort months chronologically
            for month in sorted(monthly_data.keys()):
                try:
                    value = float(monthly_data[month]['stats'][stat_name])
                except (ValueError, KeyError):
                    value = 0

                if view_type == 'increments':
                    if prev_value is not None:
                        # Monthly change - skip first data point
                        data_points.append([month, value - prev_value])
                elif view_type == 'rate':
                    if prev_value is not None and prev_value > 0:
                        # Growth rate percentage - skip first data point
                        rate = ((value - prev_value) / prev_value) * 100
                        data_points.append([month, rate])
                else:
                    # Absolute values (always include all data points)
                    data_points.append([month, value])

                prev_value = value

            if data_points:
                results.append({
                    'stat_name': stat_name,
                    'data_points': data_points,
                    'trainer_name': trainer_name
                })

        if len(results) == 1:
            # Single stat response
            return jsonify(results[0])
        else:
            # Multiple stats response
            return jsonify({
                'trainer_name': trainer_name,
                'stats': results
            })

    except Exception as e:
        print(f"Error in get_trainer_stats: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


#@app.route('/test_survey/', methods=['GET', 'POST'])
#def fill_test_survey():
#    # Generate a stats list, either default order, or order by user's badge levels if known
#    session = Session(engine, autoflush=True)
#    stats_list = get_survey_data_in_survey_order(session=session, user="test")
#
#    PogoForm = survey_gen(stats_list, PogoStatsForm)
#    try:
#        form = PogoForm(request.form)
#        real_function_call = True  # TODO cleanup
#        # These are debug stuff...
#        print("")
#        if hasattr(request, "values"):
#            print(request.values)
#    except RuntimeError:  # likely "Working outside of request context"
#        # Presumably this is because we're testing stuff and request isn't defined.
#        form = PogoForm()
#        real_function_call = False  # TODO cleanup
#
#    # Prefill trainername field
#    if user:
#        form.trainername.data = user
#    # Button for loading a user's past submission is done in the jinja template + JS
#
#    html_out = "placeholder"
#    print("", file=sys.stderr)
#    print("DEBUG HERE - got", request.method)
#    if hasattr(request, "values"):
#        print(request.values)
#    if request.method == 'POST' and form.validate():
#        # If valid
#            # Display validation success
#            # Save in DB
#            # Display save success
#            # Redirect to user history page
#        if session:  # is set up
#            response = Response.save_response(session, response_values=request.values)
#            print("Raw saved response object:", response)  # TODO delete this? It just prints a python object identifier I think?
#            session.commit()
#            session.flush()
#
#            # From example
#            #user = User(form.username.data, form.email.data,
#            #            form.password.data)
#            #db_session.add(user)
#            html_out = "Thanks for the submission! Sorry, this isn't more complete yet.<p>" \
#                    "But here's the raw data you submitted if you want to back it up for now:<p>" \
#                    + str(request.values)
#        else:
#            print("skipped db_session.add call")
#        # TODO subsequent HTML or redirect
#
#    else:
#        print("DEBUG HERE - got", request.method)
#        print("RENDER HERE:")
#        if request_method == 'POST' and form_validated:
#            piw = print_incomplete_warning
#        else:  # GET
#            piw = lambda: ""
#
#        html_out = render_template('survey_template.html', form=form,
#                                   zip=zip, type=type, print=print,
#                                   print_incomplete_warning=piw,
#                                   )
#
#    try:
#        session.close()
#    except:
#        pass
#
#    return html_out


#app = Flask(__name__)
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///your_database.db'  # Update with your database URI
#app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
#db.init_app(app)

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
        #if not trainer_name or not max_storage.isdigit() or not current_pokemon_count.isdigit():
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
                #date_str = key.split('_', 1)[1]  # Extract date part from the key
                year_str = key[4:]  # Extract year value from the key
                age_data_entries.append(f'{year_str},{value}')
                per_year_sum += int(value)

        age_data_str = '\n'.join(age_data_entries)
        # TODO could do validation of sum of per-year values

        # Create and save survey response
        response = AgeSurveyResponse(
            trainer_id=trainer.id,
            timestamp = str(datetime.now().timestamp()),
            max_storage=int(max_storage),
            current_pokemon_count=int(current_pokemon_count),
            age_data=age_data_str
        )
        session.add(response)
        session.commit()
        session.flush()

        flash('Survey submitted successfully!')
        #return redirect(url_for('age_survey'))
        #return render_template('age_survey.html', datetime=datetime, svgplot="test_plot.svg")
        plot_data(int(max_storage), int(current_pokemon_count), age_data_str, plot_trainer_name)
        plotfile = os.path.join(PLOT_DIR, "single_survey_plot.svg")
        with open(plotfile, 'r') as fr:
            svgtext = fr.read()
        return render_template('age_survey.html', datetime=datetime, svgplot=svgtext)


    # For reference:
    #        html_out = render_template('survey_template.html', form=form,
    #                                   zip=zip, type=type, print=print,
    #                                   print_incomplete_warning=piw,
    #                                   )
    # For GET request, render the survey form
    return render_template('age_survey.html', datetime=datetime)


def plot_data(max_storage, current_pokemon_count, age_data_str, trainer=None):
    # TODO make use of current_pokemon_count
    # Create the plot
    prev_mons = current_pokemon_count
    mons = []
    data = []
    currdate = datetime.now().date()
    print("uhhh")
    print(age_data_str)
    dates = []
    for line in age_data_str.splitlines():
        a,b = line.split(",")
        delta = int(currdate.year) - int(a)
        dates.append(delta)
        data.append(int(b))
        #mons.append(max_storage - int(b))
        mons.append(prev_mons)# - int(b))
        prev_mons -= int(b)

    # Create the plot
    fig, axen = plt.subplots(2)
    ax1, ax2 = axen
    ax1.plot(dates, mons, label=f"Pokémon age distribution{' for ' + trainer if trainer else ''}", marker='o')
    ax1.plot(*zip(*[(d, max_storage) for d in dates]), label=None)
    #ax1.set_xlabel("Age > X years")
    ax1.set_ylabel("Cumulative # of mons\nolder than X years")
    ax1.set_title("Pokémon age distribution")
    ax1.grid(True)
    #ax1.legend()
    ax2.plot(dates, data, label="Pokemon age distribution", marker='o')
    ax2.set_xlabel("Age (years)")
    ax2.set_ylabel("# of mons about X\nyears old")
    #ax2.set_title("Pokemon age distribution")
    ax2.grid(True)
    plt.ylim(ymin=0)

    # Save the figure as an SVG file
    plotfile = os.path.join(PLOT_DIR, "single_survey_plot.svg")
    fig.savefig(plotfile, format="svg")

    print(f"SVG plot saved as '{plotfile}'")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("secret_key", action='store')
    parser.add_argument("--test-get-survey-data", action='store_true',
                        help="Test just the loading of the survey data, to verify e.g. "
                        "it's in the order expected.")
    parser.add_argument("--test-user", action='store', default=None)
    args = parser.parse_args()

    if True: # Later can support alternate
        db_specifier = LOCAL_DB_SPECIFIER
        print(f"Using: {LOCAL_DB_SPECIFIER}")

    engine = create_engine(db_specifier)

    if args.test_get_survey_data:
        # Why autoflush?
        session = Session(engine, autoflush=True)
        get_survey_data_in_survey_order(session, user=args.test_user)
        exit(0)

    app.secret_key = args.secret_key

    try:
        app.run()
    except (BaseException, Exception) as e:
        # TODO no cleanup here; used to do cleanup on a global session object here...
        print("Cleanup finished successfully!")

else:
    print("Note that db saving isn't set up")
    print("WARNING TEST MODE - SECRET KEY NOT SECURE")
    app.secret_key = "UNSET"

