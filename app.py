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
		if file.filename == '':
			print('No selected file')
			return 
		if file:
			json_ = file.read()
			json_ = json_to_json(json_,tokenizer=tokenizer,parser=parser)
			return(json_to_response(json_))
	
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
	
def json_to_json(json_,tokenizer,parser,):
	"""Coordinates the entire pipeline"""

	verbose("Starting pipeline")
	
	# TODO: alrighty, this is where we're starting
	# I need some pre-annotated text
	# so let's try some OGER JSON output
	# Use them as tokens for a new spaCy object

	try:
		verbose("Convert JSON to spaCy...")
		doc = json_to_spacy(json_, tokenizer=tokenizer, parser=parser)

		verbose("Convert spaCy to JSON...")
		json_ = spacy_to_json(doc,annotations=json_)
		verbose("Producing JSON:\n{}\n".format(json_))

		return(json_)
	except Exception as e:
		raise(e)
		
def json_to_spacy(json_,tokenizer=False,parser=False):
	json_ = json.loads(json_)
	text = json_['text']

	if not tokenizer:
		tokenizer = spacy.load('en',disable=['parser','ner'])

	if not parser:
		parser = spacy.load('en',disable=['tagger'])

	denotations = []
	# start, end, length, id
	for denotation in json_['denotations']:
		id_ = denotation['id']
		begin = denotation['span']['begin']
		end = denotation['span']['end']
		length = end - begin
		obj = denotation['obj']
		denotations.append({'id':id_,'begin':begin,'end':end,'length':length, 'obj':obj})

	denotations_begins = {}
	for denotation in denotations:
		if denotation['begin'] not in denotations_begins:
			denotations_begins[denotation['begin']] = []
		denotations_begins[denotation['begin']].append(denotation)

	longest_denotations = []
	current = -1
	for key, denotations in denotations_begins.items():
		if denotations[0]['begin'] > current:
			longest_denotation = max(denotations, key = lambda i: i['length'])
			longest_denotations.append(longest_denotation)
			current = longest_denotation['end']

	tokens = []
	tokens_ws = []
	current_denotation = 0
	advancement = 0
	endgame = False
	for token in tokenizer(text):
		if token.idx < advancement:
			continue

		if token.idx + len(token.text_with_ws) <= longest_denotations[current_denotation]['begin'] or endgame:
			tokens.append(token.text)
			tokens_ws.append(len(token.text) != len(token.text_with_ws))

		else:
			begin = longest_denotations[current_denotation]['begin']
			end = longest_denotations[current_denotation]['end']
			token_text = text[begin:end]
			tokens.append(token_text)
			tokens_ws.append(text[end:end+1] == ' ')

			advancement = end

			if current_denotation + 1 < len(longest_denotations):
				current_denotation += 1
			else:
				endgame = True

	doc = spacy.tokens.Doc(tokenizer.vocab, words=tokens,
		  spaces=tokens_ws)

	for name, proc in parser.pipeline:
		doc = proc(doc)

	return doc
		
def spacy_to_json(doc,text=False,annotations=False):
	"""Given a spaCy doc object, produce PubAnnotate JSON, that can be read by TextAE
	   If original text is provided, original positions will be computed.
	   If other annotations are provided, they will be included."""

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

	if annotations:
		annos = json.loads(annotations)
		if 'denotations' in annos:
			deno_ids = set([deno['id'] for deno in pre_json['denotations']])
			new_deno_ids = set([deno['id'] for deno in annos['denotations']])
			if deno_ids.intersection(new_deno_ids): 
				for denotation in annos['denotations']:
					denotation['id'] = denotation['id'] + '*'

				if 'relations' in annos:
					for relation in annos['relations']:
						try:
							relation['id'] = relation['id'] + '*'
							relation['obj'] = relation['obj'] + '*'
							relation['subj'] = relation['obj'] + '*'
						except:
							i=0

			pre_json["denotations"].extend(annos['denotations'])



		if 'relations' in annos:
			rel_ids = set([rel['id'] for rel in pre_json['relations']])
			new_rel_ids = set([rel['id'] for rel in annos['relations']])
			if rel_ids.intersection(new_rel_ids): 
				for relation in annos['relations']:
					relation['id'] = relation['id'] + '*'
			pre_json["relations"].extend(annos['relations'])
		if 'text' in annos and pre_json['text'] == False:
			pre_json['text'] = annos['text']

	return(json.dumps(pre_json,sort_keys=True))
	
if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('-v','--verbose' , action="store_true" ,
						dest="verbose" , default=False ,
						help="Activates loading and debug messages")
	arguments = parser.parse_args(sys.argv[1:])
	
	tokenizer = spacy.load('en',disable=['parser','ner'])
	parser = spacy.load('en',disable=['tokenizer'])
	app.run(host='0.0.0.0', port=61455, debug=True)