from pymcdm.helpers import rrankdata
import numpy as np
from pymcdm.helpers import rrankdata
from pymcdm.methods import TOPSIS, VIKOR, PROMETHEE_II, COPRAS, SPOTIS, COCOSO, CODAS, MOORA
from pymoo.algorithms.nsga2 import NSGA2
from pymoo.optimize import minimize
from pymoo.visualization.scatter import Scatter
from pyod.utils.utility import standardizer
from scipy.io import loadmat
from sklearn.metrics import average_precision_score
from sklearn.model_selection import train_test_split
from scipy.io import arff
import pandas as pd
import cad_snn
import context_values
from nsga_con import ContextSearch
from nsga_con import MySampling, MyMutation, BinaryCrossover


def find_combinations(num_of_features, n):
    combination_list = [i for i in range(num_of_features)]
    results = []
    for i in range(n, len(combination_list) + 1):
        context = combination_list[i - n:i]
        behaviour = []
        behaviour.extend(combination_list[:i - n])
        behaviour.extend(combination_list[i:])
        results.append([context, behaviour])
        results.append([behaviour, context])

    return results


def find_combinations_multi(num_of_features, n):
    results = []
    if n < num_of_features / 2:
        for i in range(n, int(num_of_features / 2) + n):
            res = find_combinations(num_of_features, i)
            results.extend(res)
    else:
        results = find_combinations(num_of_features, n)
    return results


def test(true_context, X_train_original, X_test_original, y_test, k, dist='cosine'):
    contextual_data_train = X_train_original[:, true_context[0]]
    behavioral_data_train = X_train_original[:, true_context[1]]
    contextual_data_test = X_test_original[:, true_context[0]]
    behavioral_data_test = X_test_original[:, true_context[1]]

    neighbors_con = cad_snn.nearest_neighbours(contextual_data_train, k)
    nn_con_train = neighbors_con.kneighbors(None, k, return_distance=False)
    nn_con_test = neighbors_con.kneighbors(contextual_data_test, k, return_distance=False)

    matrix_train = cad_snn.find_snn_distance(behavioral_data_train, behavioral_data_train, nn_con_train,
                                             nn_con_train, nn_con_train, k, dist=dist)
    matrix_test = cad_snn.find_snn_distance(behavioral_data_train, behavioral_data_test, nn_con_test,
                                            nn_con_train, nn_con_test, k, dist=dist)

    caf_scores = []

    for i in range(len(contextual_data_test)):
        caf = cad_snn.contextual_anomaly_factor(matrix_train, matrix_test, nn_con_test, i)
        caf_scores.append(caf)
    return caf_scores, average_precision_score(y_test, caf_scores)


def get_topsis_list(indexes, values):
    model = TOPSIS()
    types = np.array([-1, -1, -1])
    pref = model(values, np.array([1, 2, 1]), types)
    ranking = rrankdata(pref)
    order = np.argsort(ranking)
    indexes = np.asarray(indexes)
    indexes = indexes[order]
    return indexes


def context_search(c_list):
    L = [i for i in range(len(c_list))]
    L = np.asarray(L)
    n_max = 4
    problem = ContextSearch(L, n_max, c_list, data)
    if len(c_list) < 1000:
        pop_size = 20
    else:
        pop_size = 50
    algorithm = NSGA2(
        pop_size=pop_size,
        sampling=MySampling(),
        crossover=BinaryCrossover(),
        mutation=MyMutation(),
        eliminate_duplicates=True)
    res = minimize(problem,
                   algorithm,
                   ('n_gen', 10),
                   seed=1,
                   verbose=True)

    Scatter().add(res.F).show()
    con_indexes = []

    for a in res.X:
        y = np.where(a)
        con_indexes.append(y[0].tolist())

    context_vals = res.F.tolist()
    context_vals = np.array(context_vals)
    context_names = context_values.index_to_context(con_indexes, c_list)
    return context_vals, context_names


def run_test(con_names, n, test_size, k=40):
    acc_array = []
    for i in range(n):
        random_state = np.random.RandomState(i)
        arr = []
        hash_table_scores = dict()
        if test_size == 1:
            X_train_original = data
            X_test_original = data
            y_test = ground_truth
            X_train_norm, X_test_norm = standardizer(X_train_original, X_test_original)
        else:
            X_train_original, X_test_original, y_train, y_test = train_test_split(data, ground_truth,
                                                                                  test_size=test_size,
                                                                                  stratify=ground_truth,
                                                                                  random_state=random_state)
            X_train_norm, X_test_norm = standardizer(X_train_original, X_test_original)

        for all_contexts in con_names:
            caf_list = []
            keys = []
            for j, c in enumerate(all_contexts):
                key = context_values.find_key(c, context_list)
                if hash_table_scores.get(key) is not None:
                    scores = hash_table_scores[key]

                else:
                    scores, acc = test(c, X_train_norm, X_test_norm, y_test, k, "cosine")
                    hash_table_scores[key] = scores

                caf_list.append(scores)
                keys.append(key)

            scores_mean = cad_snn.score_combination_mean(caf_list)

            arr.append(average_precision_score(y_test, scores_mean))

        acc_array.append(arr)
    acc_array2 = np.asarray(acc_array)

    return np.mean(acc_array2, axis=0)


# print('ion 5 arff')
mat = loadmat('datasets_odds/pima.mat')

data = mat['X']
ground_truth = mat['y'].ravel()

file_name = "pima"


# data = pd.read_csv('datasets_odds/ecoli.data', header=None, sep='\s+')
# data = data.iloc[:, 1:]
# ground_truth = data.iloc[:, 7]
# ground_truth = ground_truth.replace(['omL','imL','imS'],1)
# ground_truth = ground_truth.replace(['cp','im','imU','om','pp'],0)
# ground_truth=ground_truth.values
# data=data.iloc[:, 1:7].values

# data, meta = arff.loadarff('datasets_DAMI/Glass_withoutdupl_norm.arff')
# data = pd.DataFrame(data)
# ground_truth = data.iloc[:, -1]
# ground_truth = ground_truth.replace([b'yes'],1)
# ground_truth = ground_truth.replace([b'no'],0)
# data = pd.get_dummies(data.iloc[:, 0:-2])
# ground_truth=ground_truth.values
# data=data.values
# file_name = "ads"


p = 2
if (len(data[0]) > 40) & (len(data[0]) <= 300):
    p = 10
elif len(data[0]) > 300:
    p = 100

context_list = find_combinations_multi(len(data[0]), p)

con_vals, con_names = context_search(context_list)

rscores = run_test(con_names, n=10, test_size=0.3)
# np.savetxt("scores/ODDS/rscores_" + file_name + str(p) + ".csv", rscores, delimiter=",")
# np.savetxt("scores/ODDS/convals_" + file_name + str(p) + ".csv", con_vals, delimiter=",")

# con_vals = genfromtxt('scores/ODDS/convals_synthetic_new2.csv', delimiter=',')
# rscores = genfromtxt('scores/ODDS/rscores_synthetic_new2.csv', delimiter=',')
indexes_topsis = get_topsis_list(rscores, con_vals)
print(indexes_topsis[0])
print(np.max(indexes_topsis[0:5]))