from flask import Flask, request, redirect, jsonify
from flask.templating import render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.exc import DataError
import pandas as pd
import numpy as np
from datetime import datetime


SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root@localhost:3306/6Steps'
engine = create_engine(url=SQLALCHEMY_DATABASE_URI)
conn = engine.connect()

app = Flask(__name__)
app.debug = True
app.autoreload = True

app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI

db = SQLAlchemy(app)

class Process(db.Model):
    __tablename__ = 'Process' 
    process_id = db.Column(db.Integer, primary_key = True)
    process_name = db.Column(db.String(50))
    process_tech_name = db.Column(db.String(50))
    PBC_name = db.Column(db.String(50))
    PBC_color = db.Column(db.String(10))

    def __repr__(self):
    
        return '\n process_id: {0} process_name: {1} process_tech_name: {3} PBC_name: {4} PBC_color: {5}'.format(self.process_id, self.process_name, self.process_tech_name, self.PBC_name, self.PBC_color)


    def __str__(self):

        return '\n process_id: {0} process_name: {1} process_tech_name: {3} PBC_name: {4} PBC_color: {5}'.format(self.process_id, self.process_name, self.process_tech_name, self.PBC_name, self.PBC_color)
    
class PDR_sessions(db.Model):
    __tablename__ = 'PDR_sessions' 
    __table_args__ = (
        db.PrimaryKeyConstraint('session_id', 'process_id', 'PB_num', 'PB_code'),
    )
    session_id = db.Column(db.Integer, db.ForeignKey("Sessions.session_id"))
    process_id = db.Column(db.Integer, db.ForeignKey("Process.process_id"))
    PB_num = db.Column(db.Integer)
    PB_code = db.Column(db.String(18))
    Process_results_Min = db.Column(db.Float)
    Process_results_Max = db.Column(db.Float)
    Process_results_Ave = db.Column(db.Float)
    Process_results_sigma = db.Column(db.Float)
    Process_results_attribute = db.Column(db.String(50))
    Target_achieved = db.Column(db.Boolean)
    Rec_action_number = db.Column(db.String(20))

    def __repr__(self):
    
        return '\n session_id: {0} process_id: {1}'.format(self.session_id, self.process_id)


    def __str__(self):

        return '\n session_id: {0} process_id: {1}'.format(self.session_id, self.process_id)
    
class Sessions(db.Model):
    __tablename__ = 'Sessions'
    session_id = db.Column(db.Integer, primary_key = True)
    submit_time = db.Column(db.DateTime(timezone=False), nullable=False, default=datetime.now())
    username = db.Column(db.String(50))

    def __repr__(self):
    
        return '\n session_id: {0}'.format(self.session_id)


    def __str__(self):

        return '\n session_id: {0}'.format(self.session_id)
    
def get_dropdown_values(table_name, k, v):
    table = pd.read_sql("select * from {0}".format(table_name), conn).fillna('NA')
    table = table.groupby([k], as_index=False).agg({v: np.unique})
    class_entry_relations = {k:v if type(v) == str else list(v) for k,v in table.values}
    return class_entry_relations

@app.route('/_update_dropdown')
def update_dropdown():

    # the value of the first dropdown (selected by the user)
    selected_process = request.args.get('selected_process', type=str)

    # get values for the second dropdown
    updated_values = get_dropdown_values("Process", "process_name", "process_tech_name")[selected_process]

    # create the value sin the dropdown as a html string
    html_string_selected = ''
    for entry in updated_values:
        html_string_selected += '<option value="{}">{}</option>'.format(entry, entry)

    return jsonify(html_string_selected=html_string_selected)

def make_entries(i, row, col_names, n):
    ret = []
    for cn, entry in zip(col_names[:n], row):
        if cn == 'PB code':
            ret.append('<td style="text-align:center{0}">{1}</td> <input type="hidden"{0} value="{1}" />'.format(' name="{}_{}"'.format(cn.replace(" ","_").lower(), i), entry))
        else: ret.append('<td style="text-align:center">{}</td>'.format(entry))
    for cn in col_names[n:]:
        if cn == 'Target Achieved':
            ret.append('<td style="text-align:center"><SELECT class="form-control" name="{}_{}"> <option value="yes">yes</option> <option value="no">no</option></select></td>'.format(cn.replace(" ","_").lower(), i))
        else: ret.append('<td style="text-align:center"><input type="text" name="{}_{}"></td>'.format(cn.replace(" ","_").lower(), i))

    return " <tr> "+' '.join(ret)+" </tr> "

@app.route('/_process_data')
def process_data():
    user_name = request.args.get('user_name', type=str)
    selected_process = request.args.get('selected_process', type=str)
    selected_process_tech = request.args.get('selected_process_tech', type=str)
    selected_pbc_name = request.args.get('selected_pbc_name', type=str)
    
    process_id = Process.query.filter_by(process_name=selected_process,
                                         process_tech_name=selected_process_tech,
                                         PBC_name=selected_pbc_name,
                                        ).first().process_id
    
    query_sql = """
            select t1.PB_code, 
            `parameter (input to pdr: output response)`,
            `verification method (input to pdr)`,
            `sample size (input to pdr)`
            from (select num, PB_code 
                    from Process_PBHB_mapping 
                    where process_id = {i}) as t1
            join PB_Handbook as t2
            on t1.PB_code = t2.PB_code
            order by num
            ;""".format(i=process_id)
    pbhb_codes = [p for p in conn.execute(query_sql).fetchall()]
    columns = ['PB code', 'Parameter', 'Verification Method','Sample Size', 
               'Min', 'Max', 'Ave', 'Sigma', 'Attribute', 'Target Achieved',
               'Rec Action Number'
              ]
    
    n_fixed_cols = 4
    if user_name == '':
        html_string = """
        Please input user name
        """
    elif len(pbhb_codes) > 0:
        html_string = """
        Selection: <br><br> Process Name: {pn} <br> Process Tech Name: {pt} <br> PBC Name: {pb}
        <br><br>
        <form action="/add" method="GET">
        <input type="hidden" name="user_name" value="{u}" />
        process_id:
        <label>{i}</label>
        <input type="hidden" name="process_id" value="{i}" />
        <table class="center">
            <thead>
            <tr>
                {column_names}
            </tr>
            </thead>
            <tbody>
                {pbhb_codes}
            </tbody>
        </table>
        entries:
        <label>{n}</label>
        <input type="hidden" name="num_entries" value="{n}" />
        <div align="center">
        <button type="submit" style="color:white; background:#3498DB;">Add</button>
        </div>
        </form>
        """.format(u=user_name,
                   i=process_id,
                   pn=selected_process,
                   pt=selected_process_tech, 
                   pb=selected_pbc_name,
                   column_names=' '.join(['<th>{c}</th>'.format(c=col) for col in columns]), 
                   pbhb_codes=' '.join([make_entries(i, row, columns, n_fixed_cols) for i, row in enumerate(pbhb_codes)]),
                   n=len(pbhb_codes)
                  )
    else:
        html_string = """
        Selection: <br><br> Process Name: {pn} <br> Process Tech Name: {pt} <br> PBC Name: {pb}
        <br><br>
        NO MATCHING TEMPLATE
        """.format(i=process_id,
                   s=np.random.randint(0,1000),
                   pn=selected_process,
                   pt=selected_process_tech, 
                   pb=selected_pbc_name
                  )

    return jsonify(html_string_selected=html_string)
            

# function to add profiles
@app.route('/add', methods=["GET"])
def input_data():
    user_name = request.args.get("user_name").lower()
    process_id = request.args.get("process_id")
    entries_count = int(request.args.get("num_entries"))
    
    if process_id != '' and user_name != '' and entries_count > 0:
        sess = Sessions(username=user_name,
                       submit_time=datetime.now()
                       )
        db.session.add(sess)
        db.session.commit()
        session_id = sess.session_id
        for i in range(entries_count):
            PB_code = request.args.get("pb_code_{}".format(i))
            min_ = request.args.get("min_{}".format(i))
            max_ = request.args.get("max_{}".format(i))
            ave_ = request.args.get("ave_{}".format(i))
            sigma = request.args.get("sigma_{}".format(i))
            attribute = request.args.get("attribute_{}".format(i))
            target_achieved = request.args.get("target_achieved_{}".format(i))
            rec_action_number = request.args.get("rec_action_number_{}".format(i))
            try:
                p = PDR_sessions(session_id = session_id,
                                 process_id = process_id,
                                 PB_num = i+1,
                                 PB_code = PB_code,
                                 Process_results_Min = min_,
                                 Process_results_Max = max_,
                                 Process_results_Ave = ave_,
                                 Process_results_sigma = sigma,
                                 Process_results_attribute = attribute,
                                 Target_achieved = True if target_achieved == 'yes' else False,
                                 Rec_action_number = rec_action_number,
                                )
                db.session.add(p)
                db.session.commit()
            except DataError:
                db.session.rollback()
                del_sess = Sessions.query.get(session_id)
                db.session.delete(del_sess)
                db.session.commit()
                return redirect('/error')
    else: return redirect('/error')
    
    return redirect('/')

@app.route('/error')
def error_msg():
    return render_template('error.html')

# function to render index ppbc_name
@app.route('/')
def index():
    sessions = Sessions.query.order_by(Sessions.submit_time.desc()).all()
    return render_template('index.html', sessions=sessions)

@app.route('/pdr')
def add_data():
    processes = [p[0] for p in conn.execute("select distinct process_name from Process;").fetchall()]
    pbc_names = [p[0] for p in conn.execute("select distinct pbc_name from Process;").fetchall()]
    
    process_tech_relations = get_dropdown_values("Process", "process_name", "process_tech_name")

    default_process_tech = process_tech_relations[processes[0]]
    
    return render_template('show_pdr.html', 
                           processes=processes, 
                           pbc_names=pbc_names, 
                           process_techs=default_process_tech
                          )

@app.route('/delete/<int:session_id>')
def erase(session_id):
    
    data = PDR_sessions.query.filter_by(session_id=session_id).all()
    for d in data:
        db.session.delete(d)
        db.session.commit()
    data = Sessions.query.get(session_id)
    db.session.delete(data)
    db.session.commit()
    return redirect('/')

@app.route('/show/<int:session_id>')
def view_session_input(session_id):
    sessions = PDR_sessions.query.filter_by(session_id=session_id).order_by(PDR_sessions.PB_num).all()
    columns = ['PB code', 'Min', 'Max', 'Ave', 
               'Sigma', 'Attribute', 'Target Achieved',
               'Rec Action Number'
              ]
    return render_template('view_input_pdr.html', 
                           session_id=session_id, 
                           sessions=sessions,
                           columns=columns,
                          )

if __name__ == '__main__':
    app.run()