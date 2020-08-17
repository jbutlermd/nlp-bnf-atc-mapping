import pandas as pd
import os
import time
import datetime
import math
import configparser
import jellyfish as jf
from fuzzywuzzy import utils

config_file = '../config.ini'
config = configparser.ConfigParser()
config.read(config_file)

match_cache = {}
cache_stat = {'hit': 0, 'miss': 0, 'count': 0}


# Modified Function from StackOverflow -- written by Erfan
# Credit: https://stackoverflow.com/questions/13636848/is-it-possible-to-do-fuzzy-match-merge-with-python-pandas

def fuzzy_merge(df_1, df_2, key1, key2, scorer=jf.levenshtein_distance, threshold=90, limit=2, distance=True):
    """
    df_1 is the left table to join
    df_2 is the right table to join
    key1 is the key column of the left table
    key2 is the key column of the right table
    threshold is how close the matches should be to return a match
    limit is the amount of matches will get returned, these are sorted high to low
    """
    s = df_2['name_without_sw']

    m = df_1[key1].apply(lambda x: extract(str(x), s, scorer=scorer, limit=limit, distance=distance))
    m_revised = m.apply(lambda x: revert_original_name(x, key2))

    df_1['matches'] = m_revised
    m2 = df_1['matches'].apply(lambda x: ', '.join([atc_df.loc[i[2], 'ATC code'] for i in x]))
    m3 = df_1['matches'].apply(lambda x: ', '.join([atc_df.loc[i[2], 'ATC code'] for i in x if i[1] >= threshold]))
    df_1['atc_matches'] = m2
    df_1['atc_best_match'] = m3
    df_1['matches_count'] = df_1['matches'].apply(lambda x: len(x))
    df_1['best_match_count'] = df_1['matches'].apply(lambda x: sum(i[1] >= threshold for i in x))

    return df_1


def revert_original_name(x, key):
    m = []
    for i in x:
        m.append((atc_df.loc[i[2], key], i[1], i[2]))
    return m


def extract(query, choices, processor=utils.full_process, scorer=jf.levenshtein_distance, limit=5, distance=True):
    tmp = choices.to_frame('name')
    tmp['name'] = tmp['name'].apply(lambda x: processor(x))
    cache_stat['count'] += 1
    if query in match_cache.keys():
        # print("%s in cache" % query)
        cache_stat['hit'] += 1
        return match_cache[query]
    else:
        # print("searching %s" % query)
        cache_stat['miss'] += 1
        tmp['distance'] = tmp['name'].apply(lambda x: scorer(remove_stop_words(processor(query)), str(x)))
        if distance:
            tmp['score'] = tmp.apply(lambda x: calculate_score(x['distance'], query, x['name']), axis=1)
        else:
            tmp['score'] = tmp['distance'].apply(lambda x: round(x * 100))

        tmp.sort_values(by=['score'], ascending=False, inplace=True)

        results = tmp[0:limit]
        best_results = []
        for key, value in results.iterrows():
            best_results.append((value['name'], value['score'], key))
        match_cache[query] = best_results
        return best_results


def remove_stop_words(x):
    if x not in whitelist:
        x_tokenized = x.split(" ")
        itertokens = iter(x_tokenized)
        next(itertokens)
        tokens_without_sw = [word for word in itertokens if word not in stop_words]
        tokens_without_sw.insert(0, x_tokenized[0])
        text_without_sw = " ".join(tokens_without_sw)
        return text_without_sw
    else:
        return x


def calculate_score(distance, x, y):
    return (1 - distance / max(len(x), len(y))) * 100


def number_format(x):
    if x - math.trunc(x) > 0:
        return '{:.2f}'.format(x)
    else:
        return '{:.0f}'.format(x)


def control_scorer(a, b):
    if a.lower() == b.lower():
        return 1
    else:
        return 0


start_time = time.time()
# Load source file
bnf_df = pd.read_csv(os.path.join(config['DEFAULT']['output_dir'], 'bnf_code_clean.csv'))
# bnf_df = pd.read_csv(os.path.join(config['DEFAULT']['output_dir'], 'bnf_code_test_file.csv'))

# Load stop words and whitelist
stop_words = pd.read_csv(os.path.join('../data/stop_words.csv'), header=None)[0].values.tolist()
whitelist = pd.read_csv(os.path.join('../data/whitelist.csv'), header=None)[0].values.tolist()

# Load RxNorm ATC data file
atc_df = pd.read_csv('../data/rxnorm_atc_code_info.csv')
atc_df.columns = ['i', 'rxcui', 'rxaui', 'sab', 'tty', 'ATC code', 'ATC level name', 'suppress']
atc_df.drop('i', axis=1, inplace=True)
atc_df = atc_df.loc[atc_df['tty'].isin(['IN', 'RXN_IN'])]
atc_df['name_without_sw'] = atc_df['ATC level name'].apply(lambda x: remove_stop_words(x))

# Perform similarity match of the full file

scorer_list = [control_scorer, jf.levenshtein_distance, jf.damerau_levenshtein_distance, jf.jaro_distance,
               jf.jaro_winkler, jf.hamming_distance]
scorer_title = ["Control", "Levenshtein", "Damerau-Levenshtein", "Jaro", "Jaro-Winkler", "Hamming"]
scorer_type = [False, True, True, False, False, True]

i = 2

header = f"\nPerforming similarity match of the full file using %s algorithm\n" % scorer_title[i]
underscore = "-" * len(header)
print(header + underscore)

merged_df = fuzzy_merge(bnf_df, atc_df, 'bnf_chemical_substance', 'ATC level name', threshold=95, limit=10,
                        scorer=scorer_list[i], distance=scorer_type[i])
print(merged_df.head(5))

merged_df.to_csv(os.path.join(config['DEFAULT']['output_dir'], 'full-bnf-atc-output.csv'))

end_time = time.time()
uptime = end_time - start_time
human_uptime = str(datetime.timedelta(seconds=int(uptime)))
print('Similarity matching & merging is completed.')
print(f'Total Time Elapsed: {human_uptime}')
print(f"Total call count: {cache_stat['count']}")
print(f"Total cache hit: {cache_stat['hit']}")
print(f"Total cache miss: {cache_stat['miss']}")
