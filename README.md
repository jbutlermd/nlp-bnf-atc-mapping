# About nlp-bnf-atc-mapping
This repository accompanies the paper entitled "[TBD]" which investigates the usage of different NLP methodologies to accurately map the British National Formulatory (BNF) code to Anatomical Therapeutic Chemical (ATC) classification code.  The source code given within this project automates the mapping and creates confusion matrix for the investigator to curate the resulting mapping to determine the performance for each algorithm.

### Data Source

The data source listed below is needed to replicate the project results and can be used in your own project as well.


1. [BNF Code Information CSV File](https://apps.nhsbsa.nhs.uk/infosystems/welcome) - Log in as guest, click on "+ Data" button, click on Drug Data, click on BNF Code Information.  Select the most recent version and download the data.  Extract the file and rename it to `BNF_Code_Information.csv`.

2. [ATC Data File](https://www.whocc.no/atc_ddd_index_and_guidelines/order/) - Data file containing ATC codes which can be purchased for 200 euros and will need to be converted into CSV file for the project (see instructions below).

*Optional* - If you want to extract ATC codes to generate cross-reference data file which is already provided in this archive.

3. [RXNorm Files](https://www.nlm.nih.gov/research/umls/rxnorm/docs/rxnormfiles.html) - An account with ULMS is required to download the archive (the registration is free).  Download the most recent **RXNorm Full Monthly Release**.  Please refer to [database install script](https://www.nlm.nih.gov/research/umls/rxnorm/docs/techdoc.html#s13_0) instructions to automate the loading of the RxNorm data into the database.  The script can be [downloaded here](https://download.nlm.nih.gov/rxnorm/terminology_download_script.zip). It will take a while to completely load and index the entire database.  MySql 5.7 was used in this project and is recommended to use for the study replication.

### Set up
1. Clone this git repository
```bash
git clone https://github.com/jbutlermd/nlp-bnf-atc-mapping.git
```
2. Install required python packages
```bash
cd nlp-bnf-atc-mapping
pip -r requirements.txt
```
3. Set up configuration file
```bash
cp config-sample.ini config.ini
```
4. Change configuration settings according to your system setup
```bash
vi config.ini
```
### Jupyter Notebook
Jupyter notebook files are provided in this repository (in the `notebook` folder) to aid with the data cleaning and preparing the files for use by analysis scripts.

`atc_whocc.ipynb` - Converts ATC/DDD publication file from WHOCC website to CSV file used by other scripts.


### Execute Scripts
1. Before running mapping scripts, you will need to prepare a data file first:
```bash
python clean_bnf.py
```

2. Execute the scripts
```bash
python method-fuzzywuzzy.py
python method-jellyfish.py
python full-map-fuzzywuzzy.py
python full-map-jellffish.py
``` 
