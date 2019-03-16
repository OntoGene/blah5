from flask import Flask, request, make_response
import spacy

import argparse , sys
import datetime
import json

ERROR_FILE = 'error.log'

NO_TEXT_ERROR = """No 'text' to process supplied. Use ?text=This+is+an+example."""
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
@app.route('/', methods=['POST'])
def server():
	
	# so it's hiding in request.get_json()
	
	# curl -F file='@data/6234315.json' https://pub.cl.uzh.ch/projects/ontogene/blah5/ > out.json
	# curl -F file='@data/6234315.json' http://0.0.0.0:61455/ > out.json
	if 'file' in request.files:
		verbose('request.files')
		# check if the post request has the file part
		file_ = request.files['file']
		if file_.filename == '':
			verbose('No selected file')
		if file_:
			json_ = file_.read()
			json_ = json_to_json(json_,tokenizer=tokenizer,parser=parser)
			return(json_to_response(json_))
	
	# curl -H "Content-type:Application/json" -d '{"text":"example text"}' https://pub.cl.uzh.ch/projects/ontogene/blah5/
	if 'application/json' in request.headers['CONTENT_TYPE'].lower():
		verbose('request.get_json()')
		json_ = request.get_json()
		try:
			json_ = json_to_json(json_, tokenizer, parser)
			return(json_to_response(json_))
		except Exception as e:
			error_log(e)
			return("Error while processing request for '{}'. Check {} for more information.\n".format(request.get_json()['text'],ERROR_FILE),500)
		
	# curl -d text="example text"   https://pub.cl.uzh.ch/projects/ontogene/blah5/
	if 'text' in request.form:
		verbose('request.form')
		try:
			json_ = text_to_json(request.form['text'])
			json_ = json_to_json(json_, tokenizer, parser)
			return(json_to_response(json_))
		except Exception as e:
			error_log(e)
			return("Error while processing request for '{}'. Check {} for more information.\n".format(request.form['text'],ERROR_FILE),500)		
	return("Unsupported media type.",415)

def text_to_json(text):
	json_ = '''{"text":"''' + text + '''"}'''
	return json_

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
	try:
		json_ = str(json_,encoding="utf-8")
	except Exception:
		pass
	
	try:
		json_ = json.loads(json_)
	except Exception:
		pass
	text = json_['text'].strip()

	if not tokenizer:
		tokenizer = spacy.load('en',disable=['parser','ner'])

	if not parser:
		parser = spacy.load('en',disable=['tagger'])

	if 'denotations' in json_:
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
	
	else:
		tokens=[str(token.text) for token in tokenizer(text)]		
		doc = spacy.tokens.Doc(tokenizer.vocab, words=tokens)

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
		try:
			annotations = str(annotations,encoding="utf-8")
		except Exception:
			pass
		
		try:
			annos = json.loads(annotations)
		except:
			annos = annotations
			
		

		if 'denotations' in annos and False:

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
							pass

			pre_json["denotations"].extend(annos['denotations'])

		
		if 'relations' in annos and False:
			rel_ids = set([rel['id'] for rel in pre_json['relations']])
			new_rel_ids = set([rel['id'] for rel in annos['relations']])
			if rel_ids.intersection(new_rel_ids): 
				for relation in annos['relations']:
					relation['id'] = relation['id'] + '*'
			pre_json["relations"].extend(annos['relations'])
		
		pre_json['text'] = doc.text
		for token in doc:
			if '5' in token.text:
				print(token)
	pre_json = post_process(pre_json)

	return(json.dumps(pre_json,sort_keys=True))
	
def post_process(json_):
	if 'relations' in json_:
		for relation in json_['relations']:
			if relation['pred'] == '':
				relation['pred'] = 'unspecified'
	return json_
	
if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('-v','--verbose' , action="store_true" ,
						dest="verbose" , default=False ,
						help="Activates loading and debug messages")
	arguments = parser.parse_args(sys.argv[1:])
	
	tokenizer = spacy.load('en',disable=['parser','ner'])
	parser = spacy.load('en',disable=['tokenizer'])
	app.run(host='0.0.0.0', port=61455, debug=True)