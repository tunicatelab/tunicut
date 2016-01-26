from optparse import OptionParser
import re
import sqlite3
from Bio.Seq import Seq
parser=OptionParser()

parser.add_option("-f", "--fasta", action="store", type="string", dest="fasta", help="fasta file containing scaffold sequences")

parser.add_option("-d", "--database", action="store", type="string", dest="database", help="Name of database that will contain guides")

parser.add_option("-o", "--output", action="store", type="string", dest="output", help="name of output file")

parser.add_option("-t", "--training_data", action = "store", type="string", dest="training_data", help="training data")

parser.add_option("-c", "--complete_data", action="store", type="string", dest="complete_data", help="complete data file")
(options, args) = parser.parse_args()

def ReadScaffold(scaffold_filename):
    """This function will allow the user to read the Joined Scaffold Fasta file in the same way it allows them
    to read the KH fasta file. The sequence for each scaffold will be stored as a dictionary"""

    print ("Opening {}.......".format(scaffold_filename))

    print ("Reading {}.......".format(scaffold_filename))

    with open(scaffold_filename) as in_handle:
        contents=in_handle.read() #read file

    entries=contents.split('>')[1:] #split using ">"

    part_entries=(entry.partition("\n") for entry in entries) #part_entries is a generator object

    pair=[[entry[0],entry[2].replace("\n","")] for entry in part_entries] #name of sequence and sequence

    ScaffoldSequence={}

    print ("Creating ScaffoldSequence Dictionary")

    for seq in pair:
        ScaffoldSequence[str(seq[0])]=str(seq[1])

    return(ScaffoldSequence)

Scaffolds=ReadScaffold(options.fasta)

def findgRNA(ScaffoldDict):

    connection = sqlite3.connect(options.database)  #make connection to database

    cur= connection.cursor()

    cur.execute("CREATE TABLE TemplateguideRNA (Scaffold char, Strand char, PAM char, Start integer, End integer, guideRNA text)")
    cur.execute("CREATE TABLE NonTemplateguideRNA (Scaffold char, Strand char, PAM char, Start integer, End integer, guideRNA text)")


    for scaffoldsID in ScaffoldDict.keys():

        sequence=ScaffoldDict[scaffoldsID] #store sequence

        TemplateSites=re.findall( r'(?=([ATGC]{20}GG))', sequence[10:len(sequence)-10] )  #NGG guideRNAs

        NonTemplateSites=re.findall( r'(?=(CC[ATGC]{20}))', sequence[10:len(sequence)-10] )   #CCN guideRNAs

        TemplateSitesPositions=[ int( num.start() + 1) for num in re.finditer( r'(?=([ATGC]{20}GG))', sequence[10:len(sequence)-10] )  ] #NGG guideRNAs positions

        NonTemplateSitesPositions=[ int( num.start() + 1) for num in re.finditer( r'(?=(CC[ATGC]{20}))', sequence[10:len(sequence)-10]) ]  #CCN guideRNAs positions

        TemplateGuideRNAName = [ scaffoldsID+str(position)+":"+str(position+19)  for position in TemplateSitesPositions]   #names for NGG guideRNAs

        NonTemplateGuideRNAName = [ scaffoldsID+str(position)+":"+str(position+19)  for position in NonTemplateSitesPositions]   #names for CCN guideRNAs

        sequence43bpT = [sequence[i-12+10:i+31+10] for i in TemplateSitesPositions]
        #replace first nt in the guide to "G"[10:len(sequence)-10]
        sequence43bpTcorrected = [str(i[:10]+"G"+i[11:]) for i in sequence43bpT]
        #CCN guides
        sequence43bpNT = [sequence[i-11+10:i+32+10] for i in NonTemplateSitesPositions]
        #replace first 32nt with "C"[10:len(sequence)-10]
        sequence43bpNTcorrected = [str(Seq(str(i[:32]+"C"+i[33:])).reverse_complement()) for i in sequence43bpNT]
        #take reverse complement
        #TemplatePAMs = [i[30:33] for i in sequence43bpTcorrected]

        #NonTemplatePAMs = [i[10:13] for i in sequence43bpNTcorrected]

        for num in range(len(TemplateSites)):

            if not re.search(r'(?=TTT)', TemplateSites[num]):

                TemplateValues = ( scaffoldsID, "+", sequence43bpTcorrected[num][30:33], TemplateSitesPositions[num]+10 , TemplateSitesPositions[num]+18+10, sequence43bpTcorrected[num])#, TemplateURLGuideRNA )

                cur.execute("INSERT INTO TemplateguideRNA (Scaffold, Strand, PAM, Start, End, guideRNA) values (?,?,?,?,?,?) ", TemplateValues)

                """with open("TemplategRNA.gff3", "w") as handle:
                    handle.write(TemplateValues[0]+"\t"+"gRNA"+"\t"+str(TemplateValues[1])+"\t"+str(TemplateValues[2])+"\t")
        handle.close() """

        for num in range(len(NonTemplateSites)):

            if not re.search(r'(?=AAA)', NonTemplateSites[num]):

                NonTemplateValues = ( scaffoldsID, "-", sequence43bpNT[num][10:13], NonTemplateSitesPositions[num]+13 , NonTemplateSitesPositions[num]+18+13, sequence43bpNTcorrected[num])#, NonTemplateURLGuideRNA )

                cur.execute("INSERT INTO NonTemplateguideRNA (Scaffold, Strand, PAM, Start, End, guideRNA) values (?,?,?,?,?,?) ", NonTemplateValues)

    connection.commit()

findgRNA(Scaffolds)

#save sequences from database

new_connection = sqlite3.connect(options.database)
c = new_connection.cursor()
TempSequences=[guide[0] for guide in c.execute("SELECT guideRNA FROM TemplateguideRNA")]

NonTempSequences=[guide[0] for guide in c.execute("SELECT guideRNA FROM NonTemplateguideRNA")]

TestSequencesForPredictions = TempSequences + NonTempSequences



#machine learning


from sklearn.preprocessing import OneHotEncoder
from sklearn import linear_model
from sklearn import cross_validation
import numpy as np
import itertools
import seaborn as sns
import pandas as pd
from sklearn import metrics

#READ IN MUTAGENESIS DATA FROM MUTAGENESISCLIPPEDSEIGV.TSV FILE
#with open("MutagenesisSEClippedIGVSheet1.tsv","r") as ReadHandle:

#    all_data = [i.strip().split("\t") for i in ReadHandle.readlines()][:78]

#or read the file as a pandas dataframe
complete_data = pd.read_csv(options.complete_data)
complete_data = complete_data.drop(complete_data.index[77:89])

#ReadHandle.close()

#read in sequences and scores
#filename = "SequencesForNucleotideEnrichmentAnalysis.txt"
with open(options.training_data, "r") as handle:
    guides = [i.strip().split("\t") for i in handle.readlines()[1:]]

#sequences are 43nt long
sequences = [str(i[3]).upper() for i in guides]+TestSequencesForPredictions

num_continuous = 0
#changing response variable to categorical
scores = [float(i[2]) for i in guides[:77]]

#guides 19nt long sequences
gRNA = [i[11:30] for i in sequences]

#PAM-proximal and distal nucleotides
pampn = [i[13:] for i in gRNA]

#g and c content of the PAM proximal nucleotides
pampn_g = [str(int(i.count("G")*100/len(i))) for i in pampn]
pampn_c = [str(int(i.count("C")*100/len(i))) for i in pampn]

#guide_gc =
#label categorical variables
replace_dict = {"A":"0","T":"1","G":"2","C":"3",\
"AA":"4", "AT":"5","AG":"6","AC":"7",\
"TA":"8","TT":"9","TG":"10","TC":"11","GA":"12","GT":"13",\
"GG":"14","GC":"15","CA":"16","CT":"17","CG":"18","CC":"19"}

g_content_dict = {"0":"20","16":"21","33":"22","50":"23","66":"24","83":"25","100":"26"}
c_content_dict = {"0":"27","16":"28","33":"29","50":"30","66":"31","83":"32","100":"33"}
#a_content_dict =
#IF YOU WANT TO ADD MORE CATEGORICAL PARAMETERS, DEFINE A DICTIONARY THAT DEFINES THE VARIABLE [34 ONWARDS], CREATE A LIST WITH THESE VARIABLES, CALL THE REPLACE_DINUCLEOTIDE FUNCTION

"""
G-content categorical variables:
0%: 20, 16%: 21, 33%: 22, 50%: 23, 66%: 24, 83%: 25, 100%: 26
C-content categorical variables:
0%: 27, 16%: 28, 33%: 29, 50%: 30, 66%: 31, 83%: 32, 100%: 33
"""


def replace_dinucleotide(list_name, replace_what, with_what):
    """
    Takes a list as input, uses pop and insert methods to replace
    specific nucleotide/di-nucleotide with a categorical number defined
    in the previous step in replace_dict.
    """
    for i,v in enumerate(list_name):
        if v == replace_what:
            list_name.pop(i)
            list_name.insert(i, int(with_what))

#replace gc-content by categorical feature def
for i in g_content_dict.keys():
    replace_dinucleotide(pampn_g, i, g_content_dict[i])

for i in c_content_dict.keys():
    replace_dinucleotide(pampn_c, i, c_content_dict[i])

#combine g and c content lists
gc_content = []
for i in range(len(sequences)):
    gc_content.append([pampn_g[i],pampn_c[i]])

#define single nucleotide features
sequences_combinations = []
for i in sequences:
    sequences_combinations.append(list(i))

#define di-nucleotide features
all_features = []
for k in range(len(sequences)):
    #itertools will create all possible di-nucleotide combinations. (43C2)

    all_features.append(sequences_combinations[k]+[''.join(j) for j in itertools.combinations(sequences[k], 2)])

no_change_all_features = all_features
#all_features now contains both single and di-nucleotide features

for lists in all_features:
    for key in replace_dict.keys():
        replace_dinucleotide(lists, key, replace_dict[key])

seq_list=[]

#IF YOU WANT TO ADD MORE FEATURES, JUST APPEND YOUR LIST IN THIS STEP.
for i in range(len(sequences)):
    seq_list.append(all_features[i]+gc_content[i])#+additional_features[i])

#test_these_seqs = np.array(seq_list[77:])
#seq_list = all_features
#seq_list = seq_list[:77]
#create numpy arrays from lists
SequenceData = np.array(seq_list)
print (SequenceData.shape)
ScoresData = np.array(scores)

#number of times each feature is present in the dataset

max_occ = np.empty(SequenceData.shape[1]-num_continuous, dtype=int)

for i in range(SequenceData.shape[1]-num_continuous):
    max_occ[i] = len(set(SequenceData[:,i]))

#occupancy of each feature in the data given as an input
occupancy={}
for i in range(SequenceData.shape[1]-num_continuous):
    occupancy[i] = list(set(SequenceData[:,i]))

mask_list = [True]*(SequenceData.shape[1]-num_continuous) + [False]*num_continuous
#setup encoder
enc = OneHotEncoder(categorical_features=np.array(mask_list))

#save one-hot encoding as array
#enc_transformed_array = enc.fit_transform(training_data).toarray()
enc_transformed_array = enc.fit_transform(SequenceData).toarray()

test_these_seq = enc_transformed_array[77:,:]
enc_transformed_array = enc_transformed_array[:77,:]

#un-comment this for random data selection
#training_data, test_data, training_scores, test_scores = cross_validation.train_test_split(enc_transformed_array, ScoresData, test_size=0.4, random_state=42)

#if you want to use top and bottom 25% data for test/train split:

training_data = np.array(list(enc_transformed_array[:28,:]) + list(enc_transformed_array[47:77,:]))

test_data = np.array(list(test_these_seq))
#test_data = np.array(list(enc_transformed_array[28:47,:]))
training_scores = np.array(list(scores)[:28] + list(scores)[47:77])

#test_scores = np.array(list(scores)[28:47])

#cross validation to get best value for alpha, cannot do this here because the model will start overfitting. Not enough data points to perform bootstrapping.

#lasso_cv = linear_model.LassoCV(fit_intercept=True, max_iter=10000, cv=20)
#lasso_cv.fit(training_data, training_scores)

clf = linear_model.Lasso(fit_intercept = True, alpha=0.005, max_iter=100000)

#fit the model
clf.fit(training_data, training_scores)

#predict scores
pred_scores = clf.predict(test_data)

pred_scores [ pred_scores < 0] = 0


TempSeqScores = pred_scores[:len(TempSequences)]
NonTempSeqScores = pred_scores[len(TempSequences):]

TempScaffold=[scaf[0] for scaf in c.execute("SELECT Scaffold FROM TemplateguideRNA")]
TempStrand=[strand[0] for strand in c.execute("SELECT Strand FROM TemplateguideRNA")]
TempPAM=[pam[0] for pam in c.execute("SELECT PAM FROM TemplateguideRNA")]

TempStart=[G_start[0] for G_start in c.execute("SELECT Start FROM TemplateguideRNA")]

TempEnd=[G_end[0] for G_end in c.execute("SELECT End FROM TemplateguideRNA")]

TempgRNA=[seq[0][11:30] for seq in c.execute("SELECT guideRNA FROM TemplateguideRNA")]

NonTempScaffold = [scaf[0] for scaf in c.execute("SELECT Scaffold FROM NonTemplateguideRNA")]
NonTempStrand=[strand[0] for strand in c.execute("SELECT Strand FROM NonTemplateguideRNA")]

NonTempPAM=[pam[0] for pam in c.execute("SELECT PAM FROM NonTemplateguideRNA")]

NonTempStart=[G_start[0] for G_start in c.execute("SELECT Start FROM NonTemplateguideRNA")]

NonTempEnd=[G_end[0] for G_end in c.execute("SELECT End FROM NonTemplateguideRNA")]

NonTempgRNA=[seq[0][11:30] for seq in c.execute("SELECT guideRNA FROM NonTemplateguideRNA")]

TempForwardPrimer = ["G"+i+"GTTTAAGAGCTATGCTGGAAACAG" for i in TempgRNA]
TempRevPrimer = [str(Seq(i).reverse_complement())+"C"+"catctataccatcggatgccttc" for i in TempgRNA]
NonTempForwardPrimer = ["G"+i+"GTTTAAGAGCTATGCTGGAAACAG" for i in NonTempgRNA]
NonTempRevPrimer = [str(Seq(i).reverse_complement())+"C"+"catctataccatcggatgccttc" for i in NonTempgRNA]

with open(options.output, "w+") as WriteHandle:
    header = "Gene\tStrand\tPAM\tStart\tEnd\tGuideRNA\tPredictedScore\tsgRNAFwdPrimer\tU6RevPrimer\n"
    WriteHandle.write(header)

    for i in range(len(TempSequences)):
        temp = TempScaffold[i]+"\t"+TempStrand[i]+"\t"+TempPAM[i]+"\t"+str(TempStart[i])+"\t"+str(TempEnd[i])+"\t"+TempgRNA[i]+"\t"+str(TempSeqScores[i])+"\t"+TempForwardPrimer[i]+"\t"+TempRevPrimer[i]+"\n"
        WriteHandle.write(temp)

    for i in range(len(NonTempSequences)):
        temp2 = NonTempScaffold[i]+"\t"+NonTempStrand[i]+"\t"+NonTempPAM[i]+"\t"+str(NonTempStart[i])+"\t"+str(NonTempEnd[i])+"\t"+NonTempgRNA[i]+"\t"+str(NonTempSeqScores[i])+"\t"+NonTempForwardPrimer[i]+"\t"+NonTempRevPrimer[i]+"\n"
        WriteHandle.write(temp2)

WriteHandle.close()