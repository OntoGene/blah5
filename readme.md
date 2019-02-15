### Installation / Running

* It's in `/mnt/storage/karr/projects/clontogene/blah5`
* Install `pip -r install requirements.txt`
* python -m spacy download en`

### Use

* `curl -F file='@data/6234315.json' http://0.0.0.0:61455/ > out.json`
* PubAnnotation style: `curl -d text="example text"   https://pub.cl.uzh.ch/projects/ontogene/blah5/`

### To Do

* Test integration with PubAnnotation
* Automatically get OGER annos
