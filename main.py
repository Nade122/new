import json
import time

from flask import Flask, request, render_template, Markup, send_from_directory, g, redirect
import sys
import os
import sqlite3
import plotly
from plotly.graph_objs import Scatter, Layout
from datetime import datetime
import time

app = Flask(__name__, static_url_path='/static', static_folder='static')
app.secret_key = "<g\x93E\xf3\xc6\xb8\xc4\x87\xff\xf6\x0fxD\x91\x13\x9e\xfe1+%\xa3"
db_path = "database.db"
WEB_PORT = 8001
ADMIN_KEY = "AdminSecretKey123"     # An HTML safe string
COLORS = ["#000000", "#A52A2A", "#7FFFD4", "#8A2BE2", "#D2691E", "#2F4F4F", "#008000"]
color_id = 0


def init_database():
    if not os.path.isfile(db_path):
        # Database does not exist. Create one
        db = sqlite3.connect(db_path)
        # Create data table
        sql = "create table data (timestamp TEXT, name TEXT, value TEXT)"
        db.execute(sql)
        db.commit()

        sql = "create table ctrl (name TEXT, value TEXT)"
        db.execute(sql)
        db.commit()
        db.close()


def query_db(db, query, args=(), one=False):
    cur = db.execute(query, args)
    rv = [dict((cur.description[idx][0], value)
               for idx, value in enumerate(row)) for row in cur.fetchall()]
    return (rv[0] if rv else None) if one else rv


def exec_db(query):
    g.db.execute(query)
    if not query.startswith('SELECT'):
        g.db.commit()


@app.before_request
def before_request():
    g.db = sqlite3.connect(db_path)


@app.teardown_request
def teardown_request(exception):
    if hasattr(g, 'db'):
        g.db.close()


def get_variable(name):
    data = None

    try:
        sql = "SELECT * FROM ctrl WHERE name = '{}'".format(name)
        data = query_db(g.db, sql, one=True)
    except Exception as exc:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print("ERROR reading data on line {}!\n\t{}".format(exc_tb.tb_lineno, exc))

    if data is not None:
        return data.get('value', '')

    return data


def get_all_variables():
    data = None

    try:
        sql = "SELECT * FROM ctrl"
        data = query_db(g.db, sql)
    except Exception as exc:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print("ERROR reading data on line {}!\n\t{}".format(exc_tb.tb_lineno, exc))

    return data


def set_variable(name, value):
    try:
        data = get_variable(name)
        if data is None:
            sql = "INSERT INTO ctrl (name, value) VALUES ('{}', '{}')".format(name, value)
        else:
            sql = "UPDATE ctrl SET value = '{}' WHERE name = '{}'".format(value, name)
        exec_db(sql)

    except Exception as exc:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print("ERROR writing data to db on line {}!\n\t{}".format(exc_tb.tb_lineno, exc))


def save_data(name, value):
    try:
        ts = datetime.timestamp(datetime.now())
        sql = "INSERT INTO data (timestamp, name, value) VALUES ('{}', '{}', '{}')" \
              "".format(ts, name, value)
        exec_db(sql)

    except Exception as exc:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print("ERROR writing data to db on line {}!\n\t{}".format(exc_tb.tb_lineno, exc))


def get_data():
    data = None

    try:
        sql = "SELECT * FROM data ORDER BY timestamp"
        data = query_db(g.db, sql)
    except Exception as exc:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        print("ERROR reading data on line {}!\n\t{}".format(exc_tb.tb_lineno, exc))

    return data


def create_plot(plot_title, data):
    global color_id

    plot_color = COLORS[color_id]

    dataDictionary = {
        "X": [],
        "Y": []
    }

    for x in data:
        dataDictionary["X"].append(x[0])
        dataDictionary["Y"].append(x[1])

    plot = plotly.offline.plot({
        "data": [Scatter(x=dataDictionary["X"], y=dataDictionary["Y"], line=dict(color=plot_color, width=2))],
        "layout": Layout(title=plot_title, height=1000, margin=dict(
            l=50,
            r=50,
            b=100,
            t=100,
            pad=4
        ))
    }, output_type='div'
    )

    # Prepare next color for next graph
    color_id += 1
    if color_id >= len(COLORS):
        color_id = 0

    return plot


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/')
def home_page():
    access_key = request.args.get('key', ' ')
    if ADMIN_KEY != access_key:
        return "Unauthorized"
    else:
        return render_template("home_page.html", key=access_key)


@app.route('/about')
def about_page():
    access_key = request.args.get('key', ' ')
    if ADMIN_KEY != access_key:
        return "Unauthorized"
    else:
        return render_template("about.html", key=access_key)


@app.route('/graphs')
def graphs():
    global color_id

    color_id = 0
    access_key = request.args.get('key', ' ')

    if ADMIN_KEY != access_key:
        return "Unauthorized"
    else:
        plot_list = []

        # get latest data
        data_list = get_data()
        if data_list is not None:
            data_dict = {}

            for data in data_list:
                timestamp = datetime.fromtimestamp(int(data["timestamp"].split('.')[0]))
                name = data["name"]
                value = float(data["value"])
                year = datetime.strftime(timestamp, '%Y')
                month = datetime.strftime(timestamp, '%B')
                day_time = datetime.strftime(timestamp, '%d, %H:%M:%S')

                name_data = data_dict.get(name, {})
                year_data = name_data.get(year, {})
                month_data = year_data.get(month, [])
                month_data.append([day_time, value])
                year_data[month] = month_data
                name_data[year] = year_data
                data_dict[name] = name_data

            for name in data_dict:
                name_data = data_dict[name]
                for year in name_data.keys():
                    year_data = name_data[year]
                    for month in year_data.keys():
                        month_data = year_data[month]
                        plot_title = "{} {}, {}".format(name, month, year)
                        plot = create_plot("", month_data)
                        plot_html = Markup(plot)
                        plot_data = {"date": year + "." + month, "plot": plot_html, "title": plot_title}
                        plot_list.append(plot_data)

        return render_template("graphs.html", plots=plot_list, key=access_key, dldid=int(time.time()))


@app.route('/datactrl')
def data_and_controls():
    global color_id

    color_id = 0
    access_key = request.args.get('key', ' ')

    if ADMIN_KEY != access_key:
        return "Unauthorized"
    else:
        data_list = get_data()
        new_list = []
        if data_list is not None:
            data_dict = {}

            for data in data_list:
                name = data["name"]
                data_dict[name] = data["value"]

            for name in data_dict.keys():
                unit = ""
                if "temperature" in name.lower():
                    unit = "??C"
                elif "moisture" in name.lower():
                    unit = "%"
                elif "humidity" in name.lower():
                    unit = "%"

                new_list.append({"name": name, "val": data_dict[name], "unit": unit})
        vars = get_all_variables()
        return render_template("datactrl.html", dldid=int(time.time()), vars=vars, key=access_key, value_list=new_list)


@app.route('/download')
def download_csv():
    data_list = get_data()
    if data_list is not None:
        data_dict = {}
        for data in data_list:
            timestamp = datetime.fromtimestamp(int(data["timestamp"].split('.')[0]))
            name = data["name"]
            value = float(data["value"])
            date = datetime.strftime(timestamp, '%Y/%b/%d %H:%M:%S')
            name_data = data_dict.get(name, [])
            name_data.append([date, value])
            data_dict[name] = name_data

        f = open("data.csv", 'w')
        for name in data_dict.keys():
            f.write("{} date, value\n".format(name))
            value = data_dict[name]
            for data in value:
                f.write("{}, {}\n".format(data[0], data[1]))
            f.write("\n\n")

        f.close()

    return send_from_directory(app.root_path, 'data.csv')


# example query: /postdata?key=AdminSecretKey123&N=data_name&V=data_value
@app.route('/postdata', methods=['GET'])
def post_data():
    access_key = request.args.get('key', ' ')

    if ADMIN_KEY != access_key:
        return "Unauthorized"

    name = request.args.get('N', None)
    value = request.args.get('V', None)

    if name is not None and value is not None:
        save_data(name, value)

    return 'ok'


# example query: /setvar?key=AdminSecretKey123&N=var_name&V=var_value
@app.route('/setvar', methods=['GET'])
def set_var():
    access_key = request.args.get('key', ' ')

    if ADMIN_KEY != access_key:
        return "Unauthorized"

    name = request.args.get('N', None)
    value = request.args.get('V', None)

    if name is not None and value is not None:
        set_variable(name, value)

    return 'ok'


# example query: /getvar?key=AdminSecretKey123&N=var_name
@app.route('/getvar', methods=['GET'])
def get_var():
    access_key = request.args.get('key', ' ')

    if ADMIN_KEY != access_key:
        return "Unauthorized"

    name = request.args.get('N', None)

    if name is not None:
        var = get_variable(name)
        if var is not None:
            return var

    return 'none'


@app.route('/cleardata', methods=['GET'])
def cleardata():
    access_key = request.args.get('key', ' ')

    if ADMIN_KEY == access_key:
        g.db.close()
        os.remove(db_path)
        init_database()

    return redirect("/?key=" + access_key)


if __name__ == '__main__':
    if not os.path.isfile(db_path):
        init_database()

    app.run(host="0.0.0.0", port=WEB_PORT, debug=True)