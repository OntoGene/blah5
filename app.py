from flask import Flask, request, make_response
from werkzeug.utils import secure_filename
import spacy

import argparse , sys
import datetime
import json

ERROR_FILE = 'error.log'

NO_TEXT_ERROR = """No 'text' to process supplied. Use spacy?text=This+is+an+example."""
NO_TEXT_ERROR_D = """No 'text' to process supplied. Use the following: curl -d text="This is an example"""

app = Flask(__name__)

#################
# HELPER FUNCTION
#################
def verbose(*args):
	try:
		if arguments.verbose:
			for arg in args:
				print(arg)
	except NameError:
		# arguments.verbose is not defined
		pass
		
def error_log(error,error_file=ERROR_FILE):
	verbose(error)
	with open(error_file,'a') as f:
		f.write(str(datetime.datetime.utcnow()) + "\n")
		try:
			f.write(str(error))
		except Exception:
			f.write("Error could not be written.")

		f.write("\n\n")

##############
# SERVER STUFF
##############
@app.route('/', methods=['GET', 'POST'])
def upload_file():
	if request.method == 'POST':
		# check if the post request has the file part
		if 'file' not in request.files:
			print('No file part')
			return
		file = request.files['file']
		# if user does not select file, browser also
		# submit an empty part without filename
		if file.filename == '':
			print('No selected file')
			return 
		if file:
			json_ = file.read()
			text = json_to_text(json_)
			json_ = text_to_json(text)
			return(json_to_response(json_))

@app.route('/spacy', methods = ['GET', 'POST'])
def rest():
	"""Used to make requests such as:
	   curl 127.0.0.1:61455/spacy?text=This+is+a+test"""

	# Request made via cURL, so we serve JSON
	verbose("Received {} request at /spacy (no trailing slash).".format(request.method))
	if request.method == 'POST' or 'curl' in request.headers['User-Agent'].lower():

		# 'text' can hide either in request.args or request.form
		if 'text' in request.args and request.args['text'] is not '':
			try:
				json_ = text_to_json(request.args['text'])
				return(json_to_response(json_))
			except Exception as e:
				error_log(e)
				return("Error while processing request for '{}'. Check {} for more information.\n".format(request.args['text'],ERROR_FILE),500)

		if 'text' in request.form and request.form['text'] is not '':
			try:
				json_ = text_to_json(request.form['text'])
				return(json_to_response(json_))
			except Exception as e:
				error_log(e)
				return("Error while processing request for '{}'. Check {} for more information.\n".format(request.form['text'],ERROR_FILE),500)

		return(NO_TEXT_ERROR,400)

@app.route('/spacy/' , methods = ['GET','POST'])
def rest_d():
	"""Make requests using curl -d, handing a 'text' to the request."""

	if request.headers['Content-Type'] == 'application/json':
		if 'text' in request.get_json():
			try:
				json_ = text_to_json(request.get_json()['text'])
				return(json_to_response(json_))
			except Exception as e:
				error_log(e)
				return("Error while processing request for '{}'. Check {} for more information.\n".format(request.get_json()['text'],ERROR_FILE),500)
		return(NO_TEXT_ERROR_D,400)

	if request.headers['Content-Type'] == 'application/x-www-form-urlencoded':
		if 'text' in request.form:
			try:
				json_ = text_to_json(request.form['text'])
				return(json_to_response(json_))
			except Exception as e:
				error_log(e)
				return("Error while processing request for '{}'. Check {} for more information.\n".format(request.form['text'],ERROR_FILE),500)
		return(NO_TEXT_ERROR_D,400)

	return("Unsupported media type.",415)
	
def json_to_response(json_):
	response = make_response(json_)

	# This is necessary to allow the REST be accessed from other domains
	response.headers['Access-Control-Allow-Origin'] = '*'

	response.headers['Content-Type'] = 'application/json'
	response.headers['Content-Length'] = len(json_)
	response.headers['X-Content-Type-Options'] = 'nosniff'
	response.headers['charset'] = 'utf-8'
	return(response)

# PROCESSING STUFF
def json_to_text(json_):
	json_ = json.loads(json_)
	text = json_['text']
	for denotation in json_['denotations']:
		begin = denotation['span']['begin']
		end = denotation['span']['end']
		print(denotation['id'],text[begin:end])
	
	tokens = []
	tokens_ws = []
	
	current_denotation = 0
	for token in nlp(text):
		if token.idx + len(token.text_with_ws) < json_['denotations']
		
		
		# print(token.text, token.idx, token.idx+len(token.text_with_ws))
		
		# print(token.text)
	
	return("I'm just a little sample sentence.")
	
def text_to_json(text):
	"""Coordinates the entire pipeline"""

	verbose("Starting pipeline on the following text: {}".format(text))
	
	# TODO: alrighty, this is where we're starting
	# I need some pre-annotated text
	# so let's try some OGER JSON output
	# Use them as tokens for a new spaCy object

	try:
		verbose("Parsing with spaCy...")
		doc = nlp(text)
		verbose("Loaded lists into spaCy\n")

		verbose("Convert spaCy to JSON...")
		json_ = spacy_to_json(doc,text)
		verbose("Producing JSON:\n{}\n".format(json_))

		return(json_)
	except Exception as e:
		raise(e)
		
def spacy_to_json(doc,text=False):
	"""Given a spaCy doc object, produce PubAnnotate JSON, that can be read by TextAE
	   If original text is provided, original positions will be computed"""

	pre_json = { "text" : text }
	pre_json["denotations"] = list()
	pre_json["relations"] = list()

	current_position = 0
	for token in doc:
		token_dict = dict()
		token_dict["id"] = "T{}".format(token.i)

		if text:
			position = text[current_position:].find(token.text)

			# token not found
			if position == -1:
				verbose("Token {} could not be found when realigning spaCy with original text.".format(token.text))
				verbose("The following text except was searched: {} (starting from position {})".format(text[current_position:],current_position))
				continue

			token_dict["span"] = { "begin" : current_position + position , "end" : current_position + position + len(token.text)}
			current_position += position + len(token.text)
		else:
			token_dict["span"] = { "begin" : token.idx , "end" : token.idx + len(token)}

		token_dict["obj"] = token.tag_
		pre_json["denotations"].append(token_dict)

		relation_dict = dict()
		relation_dict["id"] = "R{}".format(token.i)
		relation_dict["subj"] = "T{}".format(token.i)
		relation_dict["obj"] = "T{}".format(token.head.i)
		relation_dict["pred"] = token.dep_
		pre_json["relations"].append(relation_dict)

	return(json.dumps(pre_json,sort_keys=True))

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('-v','--verbose' , action="store_true" ,
						dest="verbose" , default=False ,
						help="Activates loading and debug messages")
	arguments = parser.parse_args(sys.argv[1:])
	
	nlp = spacy.load('en')
	app.run(host='0.0.0.0', port=61455, debug=True)