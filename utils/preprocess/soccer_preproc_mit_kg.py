from nltk.corpus import stopwords
import string
# import torch
import json
import os
from gensim.test.utils import datapath
from gensim.models.fasttext import load_facebook_model
import numpy as np
# from utils.utils_graph import gen_adjacency_mat, get_degree_matrix, getER_vec
from collections import defaultdict
# from utils.preprocessor import get_fuzzy_match, fuzz
from unidecode import unidecode
# from collections import OrderedDict
from preprocessor import get_fuzzy_match
#from utils import proprocessor
from args import get_args
import os

class Preprocessor:
    '''
    Preprocessor class
    '''
    # def __init__(self, data_path='/home/debanjan/submission_soccer/data/incar/', vec_dim=300,
    def __init__(self, data_path='/data2/mrony/submission_soccer/data/soccer/', vec_dim=300,
                 # fasttext_model='/home/debanjan/acl_submissions/soccerbot_acl/vocab/wiki.simple.bin'):
                 fasttext_model='/data2/mrony/submission_soccer/data/wiki.simple.bin'):
        self.data_path = data_path
        # self.max_similarity = 85
        self.vec_dim = vec_dim

        cap_path = datapath(fasttext_model)
        self.word_emb = load_facebook_model(cap_path)
        # print (self.max_er_vec)
        self.stop = set(stopwords.words('english'))
        self.punc = string.punctuation
        self.er_dict, self.global_ent, self.eo_dict, self.objlist = self.get_kg(self.data_path + 'KG/')

        self.args = get_args()
        self.train_dataset = self.get_data('train')
        self.val_dataset = self.get_data('val')
        self.test_dataset = self.get_data('test')

        self.entitites = [d['e'] for d in self.train_dataset]
        self.entitites = list(set(self.entitites))
        print("self.entities:   ",self.entitites)
        self.entities = [tmp.lower() for tmp in self.entitites]
        self.global_ent = [unidecode(tmp.lower()) for tmp in self.global_ent]
        print("self.globalent:   ",self.global_ent)
        self.allent = list(set(self.global_ent+self.entitites+self.objlist))
        #  Create the vocab
        self.vocab = defaultdict(float)

        # self.vocab[pos]
        self.get_vocab(self.train_dataset)
        self.get_vocab(self.test_dataset)
        self.get_vocab(self.val_dataset)

        # Add additional tokens to vocab
        self.vocab[self.args.unk_tok] += 1.0
        self.vocab[self.args.sos_tok] += 1.0
        # self.vocab[self.args.ent_tok] += 1.0
        self.vocab[self.args.eou_tok] += 1.0
        self.vocab[self.args.eos_tok] += 1.0
        self.vocab[self.args.no_ent_tok] += 1.0

        self.stoi = dict(zip(self.vocab.keys(), range(1, len(self.vocab)+1)))
        self.stoi[self.args.pad_tok] = 0

        self.itos = {v: k for k, v in self.stoi.items()}
        print (len(self.stoi))
        self.n_words = len(self.stoi)

        self.vectors = np.zeros((len(self.stoi), vec_dim))
        for w, w2i in self.stoi.items():
            # if w2i < self.stoi[self.args.eos_tok]:
            self.vectors[w2i] = self.get_w2v(w)
        self.ent_dict = dict(zip(self.allent, range(0, len(self.allent))))
        self.ent_dict["<no_ent>"]=len(list(self.ent_dict.keys()))
        # self.ent_dict[self.args.no_ent_tok] = 0

    def get_vocab(self, dataset):
        '''
        Get string to index for datasets
        :param dataset:
        :return:
        '''

        for conv in dataset:
            for k, v in conv.items():
                if k == 'a' or k == 'q':
                    # print (v)
                    sents = v
                    for w in sents.split():
                        # if w not in self.objects:
                            self.vocab[w] += 1.0

    def get_w2v(self, word):
        # get word2vecs
        if '_' not in word:
            return self.word_emb.wv[word]
        else:
            return self.get_avg_word2vec(word.split('_'))

    def get_avg_word2vec(self, phrase):
        """
        get Average word vectors for a given phrases
        """
        vec = np.zeros(300)
        if phrase=="":
            return vec
        # phrase = phrase.strip()  # Remove _ during similarity calculations
        for w in phrase:
            # if w not in self.stop and w not in self.punc:
            vec = vec + self.word_emb.wv[w]
        return vec / float(len(phrase))

    def get_conv(self, filename):
        '''
        load all the training data
        :param filename:
        :return:
        '''
        with open(filename, 'r') as inp:
            try:
                out_f = json.load(inp)
            except Exception:
                print (filename)
        return out_f

    def load_all_files(self, dataset):
        '''
        Get list of all files in the directory
        :param dataset:
        :return:
        '''
        dat_files = os.listdir(self.data_path + '/manually_annotated/' + dataset + '_sketch/')
        return dat_files

    @staticmethod
    def get_kg(kg_path):
        '''
        Get the KG dictionary
        :param file_name:
        :return:
        '''

        er_pair_dict = defaultdict(set)
        eo_pair_dict = defaultdict(set)
        ent_l = set()
        kgtypes = ["clubs","country"]
        obj_l = set()
        for kgt in kgtypes:
            kg_files = os.listdir(kg_path+kgt)
            for kgf in kg_files:
                with open(kg_path +kgt+"/"+ kgf, 'r',encoding="utf-8") as f:
                    kg = f.readlines()
                for t in kg:
                    e, r, o = t.lower().replace('\n', '').split('\t')
                    er_pair_dict[e+'#'+r].add(o)
                    eo_pair_dict[e+'#'+o].add(r)
                    ent_l.add(e)
                    obj_l.add(o)
        return er_pair_dict, ent_l, eo_pair_dict,list(obj_l)

    def get_data(self, dataset):
        '''
        Load conversations from files
        :param dataset:
        :return:
        '''
        data_out = []
        # found = []
        data_files = self.load_all_files(dataset)
        for dat in data_files:
            convo = self.get_conv(self.data_path + 'manually_annotated/' + dataset + '_sketch/' + dat)  # Get Conversations

            conv_hist = []
            for j, c in enumerate(convo):
                convo_dict = {}
                convo_dict['f'] = dat.replace('.json', '')
                # conv_hist = []
                if conv_hist:
                    try:
                        conv_hist.append(c['q' + str(j + 1)])
                    except Exception as e:
                        print (dat, e)
                    if self.args.use_bert:
                        convo_dict['q'] = (' '+self.args.bert_sep+' ').join(u for u in conv_hist)  # For bert
                    else:
                        convo_dict['q'] = (' '+self.args.eou_tok+' ').join(u for u in conv_hist)
                    try:
                        conv_hist.append(c['a' + str(j + 1)])
                    except Exception as e:
                        print (e, dat)
                        exit()
                else:
                    convo_dict['q'] = c['q' + str(j + 1)]
                    conv_hist.append(c['q' + str(j + 1)])
                    conv_hist.append(c['a' + str(j + 1)])
                convo_dict['q'] = convo_dict['q']
                convo_dict['_a'] = c['a' + str(j + 1)]
                convo_dict['_q'] = c['q' + str(j + 1)]
                # convo_dict['a'] = c['a' + str(j + 1)]

                # Get KG

                if c['input_ent' + str(j + 1)]:
                    convo_dict['e'] = c['input_ent' + str(j + 1)]
                else:
                    convo_dict['e'] = self.args.no_ent_tok

                convo_dict['o'] = c['obj' + str(j + 1)].split(',')
                convo_dict['r'] = c['corr_rel' + str(j + 1)].split(',')
              
                convo_dict['a'] = c["a"+str(j+1)+"_v2"]
                if convo_dict['e']:
                    _,best_entity_ans = get_fuzzy_match(convo_dict['e'], convo_dict['a'])
                    if best_entity_ans !="":
                        convo_dict['a'] = convo_dict['a'].replace(best_entity_ans, '@entity')

                # convo_dict['a'] = c["a"+str(j+1)+"_v2"]
                # if answer is empty put the original answer
                if not convo_dict['a']:
                    convo_dict['a'] = convo_dict['_a']
                data_out.append(convo_dict)

        return data_out


if __name__ == '__main__':
    preproc = Preprocessor()
    # file names
    train_preproc_file = preproc.data_path + 'preproc_files/train.npy'
    valid_preproc_file = preproc.data_path + 'preproc_files/val.npy'
    test_preproc_file = preproc.data_path + 'preproc_files/test.npy'
    stoi_f = preproc.data_path + 'preproc_files/stoi.npy'
    entity_dict_f = preproc.data_path + 'preproc_files/etoi.npy'
    w2emb_f = preproc.data_path + 'preproc_files/wemb.npy'
    # Save all files
    np.save(train_preproc_file, preproc.train_dataset)
    np.save(valid_preproc_file, preproc.val_dataset)
    np.save(test_preproc_file, preproc.test_dataset)
    np.save(stoi_f, preproc.stoi)
    np.save(entity_dict_f, preproc.ent_dict)
    np.save(w2emb_f, preproc.vectors)
