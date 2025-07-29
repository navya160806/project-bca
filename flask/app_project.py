from flask import Flask,render_template

app=Flask(__name__)
app.secret_key='supersecretmre'

@app.route('/')
def front():
    return render_template('front.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/ds')
def ds():
    return render_template('ds.html')
 

@app.route('/dd')
def dd():
    return render_template('dd.html')
 
  
@app.route('/ss')
def ss():
    return render_template('ss.html')

  
@app.route('/fee')
def fee():
    return render_template('fee.html')

@app.route('/search')
def search():
    return render_template('search.html')

@app.route('/search2')
def search2():
    return render_template('search2.html')


@app.route('/rg')
def rg():
    return render_template('rg.html')

@app.route('/noti')
def noti():
    return render_template('noti.html')

if __name__=='__main__':
    app.run(host = '0.0.0.0',port=5000,debug=True)