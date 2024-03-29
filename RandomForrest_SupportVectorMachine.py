# RF or SVM Classifier for CP and QP data   --  Mohsen Ghanbari Summer 2020
# The user should copy four files in the same directory as this file:
# 1. The oversegmentation file named irgs_to_slic.mat
# 2. The label files named labels.csv
# 3. The feature file: C.tif or feats.mat or feats.tif. By default (C.tif case), only the diagonal elements are used
# 4. labels_test.csv containing the test data

# In the case of QP data 0:C11, 1:C12_real, 2:C22, 3:C13_real, 4:C23_real, 5:C33, 6:C12_imag, 7:C13_imag, 8:C23_imag
# and in the case of CP data 0:C11, 1:C12_real, 2:C22, 3:C12_imag.
# Please follow the instruction in the program to set up these files and also to set the parameters.

import time
import numpy as np
start = time.process_time()

from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from skimage import io, data, segmentation, filters, color
from skimage.future import graph
import scipy.io
import matplotlib.pyplot as plt
import tifffile as tiff
import matplotlib
from sklearn.metrics import confusion_matrix, cohen_kappa_score, accuracy_score
import pandas as pd
import statistics
from scipy import stats as st
from sklearn.model_selection import GridSearchCV
from tkinter.filedialog import askdirectory


labels_directory = askdirectory(title='Select Folder That Contains the label file, labels.csv') # shows dialog box and return the path
labels_directory = labels_directory + "/"


#PARAMETER SETTING
RF = True# Whether the classifier is RF or, alternatively, SVM (False)
super_pix_based = True  #Whether the classification is superpixel-based or pixel based
is_there_normalization = True  #Whether the features should be normalized
# NUM_CLASSES = 6 # 1: OW/NI, 2: YI, 3: FYI, and 4: MYI (The user should put the number of classes.)
sea_ice_classification = False # This indicates the task is whether sea-ice classification (for which labels are
# collected by MAGIC) or a general classification for which the labels are collected by my code:
# labeled_data_collector_inserting_row_and_column_manually.py.
#The program assumes the user has put a csv file named labels.csv in the same directory as this python file.
# In the csv file exported from MAGIC: the labels are in the first column: 15, 1, 3, 6, 12 represent OW, NI, YI, FYI,
# and MYI, repectively. The second and third columns are column number and row number in the image.
# However, the labels are from 1 to num_classes in the csv file generated by the upper-mentioned python script, with
# num_classes being the number of classes
complex_only = False # Whether the ingested features are only covariance matrix elements, or alternatively, some features
# that are saved in a file named feats.tif. In the case of covariance matrix, the channel intensities (diagonal elements)
# are only used in the classification.
Cluste_based_testing = True # In case, the user wants their sample units to be squares around test pixels. Each test
# sample unit will be a square of "3 by 3" sqauare where the center pixel is each of the collected test pixels in the csv
# file.


#FEATURE SETUP
if complex_only:
  # mat_feat_file = scipy.io.loadmat('feats.mat')
  # feats = mat_feat_file['imag']
  #num_feats = feats.shape[2]

  cov_elements = tiff.imread('C.tif')
  num_elems = cov_elements.shape[2]
  if num_elems == 9: # QP case
    NUM_INTESITIES = 3
  elif  num_elems == 4: # CP case
    NUM_INTESITIES = 2
  feats = np.zeros((cov_elements.shape[0], cov_elements.shape[1], NUM_INTESITIES))
  if num_elems == 9: # QP case
    feats[:, :, 0] = cov_elements[:, :, 0]
    feats[:, :, 1] = cov_elements[:, :, 2]
    feats[:, :, 2] = cov_elements[:, :, 5]
  elif num_elems == 4: # CP case
    feats[:, :, 0] = cov_elements[:, :, 0]
    feats[:, :, 1] = cov_elements[:, :, 2]

  del cov_elements
  num_feats = feats.shape[2]

else: # can be a bunch of QP- or CP-derived features named feats.mat

  # mat_feat_file = scipy.io.loadmat('feats.mat')
  # feats = mat_feat_file['imag']
  feats = tiff.imread('feats.tif')
  # feats = feats[:,:,[9, 10]]
  nan_idxs = np.where(np.isnan(feats) == True)
  feats[nan_idxs] = 0
  num_feats = feats.shape[2]



#NORMALIZATION
if is_there_normalization:
  for feat in range(0, num_feats):
    min_f = np.min(feats[:, :, feat])
    max_f = np.max(feats[:, :, feat])
    feats[:, :, feat] = (feats[:, :, feat] - min_f) / (max_f - min_f)
  nan_idxs = np.where(np.isnan(feats) == True)
  feats[nan_idxs] = 0



if super_pix_based: #If the classification is to predict labels for the superpixels delineated by the segmentation image
  # OVERSEGMENTATION FILE
  matfile = scipy.io.loadmat(
    'irgs_to_slic.mat')  # This mat file contains the oversegemntation image that is obtained through
  # CP-IRGS. After segmenting the image with a certain number of classes (e.g., 50 classes), we need to label each region
  # with an exclusive label. This is done by the Matlab script that I wrote named Labeling_each_segments_in_segmentation_differently.m
  # One important thing is that you need to mask the land areas. Land areas are labeled to a really big number (10^7)
  # in the segmentation image.
  myImage = matfile['irgs_to_slic']
  del matfile

  # CONSTRUCTING A RAG
  img = myImage
  labels = myImage  # An alternative way of obtaining the file labels: labels = segmentation.slic(img)
  edge_map = filters.sobel(color.rgb2gray(img))  # check
  rag = graph.rag_boundary(labels, edge_map)

  del edge_map

  lc = graph.show_rag(labels, rag, img)
  cbar = plt.colorbar(lc)
  io.show()

  del img

  # MASKING OUT AREAS NOT TO BE PROCESSED
  there_is_land = np.any(myImage == 10000000)

  del myImage

  if there_is_land:
    num_sup_pixels = len(rag) - 1  # number of superpixels is len(rag) - 1 (excluding land areas)
  else:
    num_sup_pixels = len(rag)  # number of superpixels

  # Calculate sp_feats with the size of num_sup_pixels*n_feats. This matrix consists of the mean feature values
  sp_feats = np.zeros((num_sup_pixels, num_feats))
  for num_sp in range(0, num_sup_pixels):  # the labels of superpixels are in range [0, num_sup_pixels)
    idxs = np.where(labels == num_sp)  # gives us a tuple-typed output of rows and columns idxs[0]-->rows
    sp_feats[num_sp, :] = np.mean(feats[idxs], axis=0)  # mean of feats



#CONSTRUCTING TRAIN AND LABEL DATA
if super_pix_based:

  sp_labels = np.zeros(num_sup_pixels)

  csv_file = np.genfromtxt(labels_directory + 'labels.csv', dtype='int', delimiter=',')

  if sea_ice_classification:
    for num_labelled in range(0, csv_file.shape[0]):  # It just assigns the label of last pixel to the superpixel.
      if csv_file[num_labelled, 0] == -1:  # The pixel is unlabeled. MAGIC gives -1 when you skip the pixel.
        continue

      # (6724 / 3008) *  (2985/1875)*
      sp = labels[int((csv_file[num_labelled, 2] - 1)), int(
        (csv_file[num_labelled, 1] - 1))]  # to get the superpixel number that contains the current labeled pixel

      if sp > num_sup_pixels:  # land areas
        continue
      if csv_file[num_labelled, 0] == 15:  # OW
        sp_labels[sp] = 1
      elif csv_file[num_labelled, 0] == 1:  # NI
        sp_labels[sp] = 1
      elif csv_file[num_labelled, 0] == 3:  # YI
        sp_labels[sp] = 2
      elif csv_file[num_labelled, 0] == 6:  # FYI
        sp_labels[sp] = 3
      elif csv_file[num_labelled, 0] == 12:  # MYI
        sp_labels[sp] = 4

  else:  # general classification where labels in the csv file starts from 1 to NUM_CLASSES.
    for num_labelled in range(0, csv_file.shape[0]):
      # row = int((csv_file[num_labelled, 2] - 1) * labels.shape[0] / 19227)
      # col = int((csv_file[num_labelled, 1] - 1) * labels.shape[1] / 2710)
      row = csv_file[num_labelled, 2] - 1
      col = csv_file[num_labelled, 1] - 1
      sp = labels[row, col]  # to get the superpixel number that contains the current labeled pixel

      if sp > num_sup_pixels:  # mask areas
        continue

      sp_labels[sp] = csv_file[num_labelled, 0]

  train_sp_samples = np.where(sp_labels != 0)
  num_tr_samples = train_sp_samples[0].shape[0]

  tr_data = np.zeros((num_tr_samples, num_feats))
  tr_labels = np.zeros(num_tr_samples)

  for labeled_sp in range (0, train_sp_samples[0].shape[0]):
    tr_data[labeled_sp, :] = sp_feats[train_sp_samples[0][labeled_sp],:]
    tr_labels[labeled_sp] = sp_labels[train_sp_samples[0][labeled_sp]]


else: # pixel-based. Just reshape the feats and construct the train samples and their labels

  feat_labels = np.zeros((feats.shape[0], feats.shape[1])) # the labels that will be assigned in the following loop

  csv_file = np.genfromtxt(labels_directory + 'labels.csv', dtype='int', delimiter=',')
  num_tr_samples = csv_file.shape[0]

  if sea_ice_classification:
    for num_labelled in range(0, csv_file.shape[0]):  # It just assigns the label of last pixel to the superpixel.
      if csv_file[num_labelled, 0] == -1:  # The pixel is unlabeled. MAGIC gives -1 when you skip the pixel.
        num_tr_samples = num_tr_samples - 1
        continue

      # (6724 / 3008) *  (2985/1875)*
      row = int((csv_file[num_labelled, 2] - 1))
      col = int((csv_file[num_labelled, 1] - 1))


      if csv_file[num_labelled, 0] == 15:  # OW
        feat_labels[row, col] = 1
      elif csv_file[num_labelled, 0] == 1:  # NI
        feat_labels[row, col] = 1
      elif csv_file[num_labelled, 0] == 3:  # YI
        feat_labels[row, col] = 2
      elif csv_file[num_labelled, 0] == 6:  # FYI
        feat_labels[row, col] = 3
      elif csv_file[num_labelled, 0] == 12:  # MYI
        feat_labels[row, col] = 4

  else:  # general classification where labels in the csv file starts from 1 to NUM_CLASSES.
    for num_labelled in range(0, csv_file.shape[0]):
      # row = int((csv_file[num_labelled, 2] - 1) * labels.shape[0] / 19227)
      # col = int((csv_file[num_labelled, 1] - 1) * labels.shape[1] / 2710)
      row = csv_file[num_labelled, 2] - 1
      col = csv_file[num_labelled, 1] - 1

      feat_labels[row, col] = csv_file[num_labelled, 0]


  re_feat = np.reshape(feats, (feats.shape[0]*feats.shape[1], num_feats)) # reshaped features
  re_feat_labels = np.reshape(feat_labels, (feats.shape[0]*feats.shape[1])) # the labels reshaped

  train_data_samples = np.where(re_feat_labels != 0)
  num_tr_samples = train_data_samples[0].shape[0]

  tr_data = np.zeros((num_tr_samples, num_feats))
  tr_labels = np.zeros(num_tr_samples)

  for labeled_sp in range (0, train_data_samples[0].shape[0]):
    tr_data[labeled_sp, :] = re_feat[train_data_samples[0][labeled_sp],:]
    tr_labels[labeled_sp] = re_feat_labels[train_data_samples[0][labeled_sp]]




#TRAIN THE CLASSIFIER



# Hyperparameter tuning method 1:
# using GridSearchCV

# if RF:
#   # Number of trees in random forest
#   n_estimators = [int(x) for x in np.linspace(start=50, stop=2000, num=39)]
#   # Number of features to consider at every split
#   max_features = ['auto', 'sqrt', 'log2']
#   # Maximum number of levels in tree
#   max_depth = [int(x) for x in np.linspace(1, 110, num=50)]
#   max_depth.append(None)
#   # Minimum number of samples required to split a node
#   min_samples_split = [2, 5, 10]
#   # Minimum number of samples required at each leaf node
#   min_samples_leaf = [2, 4, 8, 12]
#   # Method of selecting samples for training each tree
#   bootstrap = [True, False]
#   # Create the random grid
#   param_grid = {'n_estimators': n_estimators,
#                  # 'max_features': max_features,
#                  # 'max_depth': max_depth,
#                  # 'min_samples_split': min_samples_split,
#                  'min_samples_leaf': min_samples_leaf,
#                  # 'bootstrap': bootstrap
#                 }
#   # Use the random grid to search for best hyperparameters
#   # First create the base model to tune
#   grid = GridSearchCV(RandomForestClassifier(), param_grid)
# else:
#   # defining parameter range
#   param_grid = {'C': [np.power(2,x) for x in np.linspace(start=-6, stop=14, num=21)],
#               'gamma': [np.power(2,x) for x in np.linspace(start=-9, stop=11, num=21)],
#               'kernel': ['rbf']}
#
#   grid = GridSearchCV(SVC(), param_grid)
#
#
# # fitting the model for grid search
# grid.fit(tr_data, tr_labels)
#
# # print best parameter after tuning
# print(grid.best_params_)
#
# # print how our model looks after hyper-parameter tuning
# print(grid.best_estimator_)




# Hyperparameter tuning method 2:
# using a grid a parameters based on half of training data as train and the rest for
# testing. The metric is the kappa coefficient

if RF:
  # Number of trees in random forest
  n_estimators = [int(x) for x in np.linspace(start=50, stop=2000, num=39)]

  # Maximum number of levels in tree
  max_depth = [int(x) for x in np.linspace(1, 110, num=50)]
  max_depth.append(None)

  # Create the random grid
  highest_kappa = -1
  param_grid = {'n_estimators': n_estimators, 'max_depth': max_depth}
  for num_est in param_grid['n_estimators']:
    for max_d in param_grid['max_depth']:
      cur_model = RandomForestClassifier(n_estimators = num_est, max_depth = max_d)
      cur_model.fit(tr_data[::2,:], tr_labels[::2]) # training with half of train data
      pred_labels_rest = cur_model.predict(tr_data[1::2,:]) # predicting the labels of the rest of train data
      cur_kappa = cohen_kappa_score(tr_labels[1::2], pred_labels_rest)
      if cur_kappa >= highest_kappa:
        highest_kappa = cur_kappa
        best_num_est = num_est
        best_max_d = max_d

  grid= RandomForestClassifier(n_estimators = best_num_est, max_depth = best_max_d)

else: # SVM
  param_grid = {'C': [np.power(2,x) for x in np.linspace(start=-6, stop=14, num=21)],
                'gamma': [np.power(2,x) for x in np.linspace(start=-9, stop=11, num=21)]}

  # Create the random grid
  highest_kappa = -1
  for para_c in param_grid['C']:
    for para_gamma in param_grid['gamma']:
      cur_model = SVC(gamma = para_gamma, C = para_c)
      cur_model.fit(tr_data[::2, :], tr_labels[::2])  # training with half of train data
      pred_labels_rest = cur_model.predict(tr_data[1::2, :])  # predicting the labels of the rest of train data
      cur_kappa = cohen_kappa_score(tr_labels[1::2], pred_labels_rest)
      if cur_kappa >= highest_kappa:
        highest_kappa = cur_kappa
        best_para_c = para_c
        best_para_gamma = para_gamma

  grid = SVC(gamma=best_para_gamma, C=best_para_c)

grid.fit(tr_data, tr_labels)




# if RF:
#   grid = RandomForestClassifier(n_estimators= 101)
# else: # SVM SVC(gamma='scale')
#   grid = SVC(gamma=64, C=8)
# grid.fit(tr_data, tr_labels)



#FEATURE IMPORTANCE
# if RF:
#   feature_imp = pd.Series(grid.feature_importances_).sort_values(ascending=False)
#   print(feature_imp)


#LABEL PREDICTION
predicted_labels = np.zeros((feats.shape[0], feats.shape[1]))
if super_pix_based:
  sp_pred = grid.predict(sp_feats) # Predicted labels for the superpixels
  for num_sp in range(0, num_sup_pixels):
    predicted_labels[np.where(labels == num_sp)] = sp_pred[num_sp]


  # PLOT RESULTS
  tr_for_plot = np.zeros((feats.shape[0], feats.shape[1]))
  for num_sp in range(0, num_sup_pixels):
    tr_for_plot[np.where(labels == num_sp)] = sp_labels[num_sp]

  p_l = np.empty_like(predicted_labels)
  p_l[:] = predicted_labels
  p_l[np.where(labels == 10000000)] = np.amax(predicted_labels) + 1  # forcing the land areas to have label=num_class+1.

  s_l = np.empty_like(labels)
  s_l[:] = labels
  s_l[np.where(labels == 10000000)] = num_sup_pixels + 1  # forcing the land areas to have a label num_sup_pixels+1.

  # custom colormap used for train image
  cmap = matplotlib.colors.ListedColormap([(1, 1, 1), (12 / 255, 7 / 255, 134 / 255), (155 / 255, 23 / 255, 158 / 255),
                                           (236 / 255, 120 / 255, 83 / 255), (239 / 255, 248 / 255, 33 / 255)],
                                          name='colors', N=None)
  fig = plt.figure()
  ax1 = fig.add_subplot(131)
  ax2 = fig.add_subplot(132)
  ax3 = fig.add_subplot(133)
  ax1.set_title('Segmentation')
  ax1.imshow(s_l)
  ax2.set_title('Train')
  ax2.imshow(tr_for_plot, cmap=cmap)
  # leg2 = ax2.legend()
  ax3.set_title('Predicted')
  ax3.imshow(p_l, cmap='plasma')
  # leg3 = ax3.legend()
  plt.show()


else: # pixel-based
  predicted_labels =  np.reshape(grid.predict(re_feat), (feats.shape[0], feats.shape[1])) # Predicted labels for the pxls

  # PLOT RESULTS
  tr_for_plot = np.zeros((feats.shape[0], feats.shape[1]))
  tr_for_plot = feat_labels

  p_l = np.empty_like(predicted_labels)
  p_l[:] = predicted_labels

  # custom colormap used for train image
  cmap = matplotlib.colors.ListedColormap([(1, 1, 1), (12 / 255, 7 / 255, 134 / 255), (155 / 255, 23 / 255, 158 / 255),
                                           (236 / 255, 120 / 255, 83 / 255), (239 / 255, 248 / 255, 33 / 255)],
                                          name='colors', N=None)
  fig = plt.figure()
  ax1 = fig.add_subplot(121)
  ax2 = fig.add_subplot(122)

  ax1.set_title('Train')
  ax1.imshow(tr_for_plot, cmap=cmap)
  # leg2 = ax2.legend()
  ax2.set_title('Predicted')
  ax2.imshow(p_l, cmap='plasma')
  # leg3 = ax3.legend()
  plt.show()


# ACCURACY ASSESSMENT: predicted_labels versus the labels labels_test.csv file
csv_file_test = np.genfromtxt('labels_test.csv', dtype = 'int', delimiter=',')

true_labels_test = np.zeros(csv_file_test.shape[0])
pred_labels_test = np.zeros_like(true_labels_test)
true_label_test_image = np.zeros_like(predicted_labels) #For plotting the test samples

for num_labled_test in range (0, csv_file_test.shape[0]):
  row_test = csv_file_test[num_labled_test, 2] - 1
  col_test = csv_file_test[num_labled_test, 1] - 1
  if Cluste_based_testing and row_test > 0 and row_test < predicted_labels.shape[0] - 1  and col_test > 0 and col_test < predicted_labels.shape[1] - 1:
    labels_in_square = [predicted_labels[row_test - 1, col_test - 1], predicted_labels[row_test - 1, col_test],
                        predicted_labels[row_test - 1, col_test + 1], predicted_labels[row_test, col_test - 1],
                        predicted_labels[row_test, col_test], predicted_labels[row_test, col_test + 1],
                        predicted_labels[row_test + 1, col_test - 1], predicted_labels[row_test + 1, col_test],
                        predicted_labels[row_test + 1, col_test + 1]]

    pred_labels_test[num_labled_test] = st.mode(labels_in_square).mode[0] #the mode of the labels in the square
    true_labels_test[num_labled_test] = csv_file_test[num_labled_test, 0]

    true_label_test_image[row_test - 1, col_test - 1] = csv_file_test[num_labled_test, 0]
    true_label_test_image[row_test - 1, col_test] = csv_file_test[num_labled_test, 0]
    true_label_test_image[row_test - 1, col_test + 1] = csv_file_test[num_labled_test, 0]
    true_label_test_image[row_test, col_test - 1] = csv_file_test[num_labled_test, 0]
    true_label_test_image[row_test, col_test] = csv_file_test[num_labled_test, 0]
    true_label_test_image[row_test, col_test + 1] = csv_file_test[num_labled_test, 0]
    true_label_test_image[row_test + 1, col_test - 1] = csv_file_test[num_labled_test, 0]
    true_label_test_image[row_test + 1, col_test] = csv_file_test[num_labled_test, 0]
    true_label_test_image[row_test + 1, col_test + 1] = csv_file_test[num_labled_test, 0]




  else:
    pred_labels_test[num_labled_test] = predicted_labels[row_test, col_test]
    true_labels_test[num_labled_test] = csv_file_test[num_labled_test, 0]
    true_label_test_image[row_test, col_test] = csv_file_test[num_labled_test, 0]

confusion = confusion_matrix(true_labels_test, pred_labels_test)
print('Confusion Matrix\n')
print(confusion)
print('\nKappa: {:.2f}\n'.format(cohen_kappa_score(true_labels_test, pred_labels_test)))
print('\nAccuracy: {:.2f}\n'.format(accuracy_score(true_labels_test, pred_labels_test)))



#SAVE RESULTS

if super_pix_based:
  matplotlib.image.imsave(labels_directory + 'Segmentation.png', s_l)
matplotlib.image.imsave(labels_directory + 'Train.png', tr_for_plot,  cmap = 'plasma')
matplotlib.image.imsave(labels_directory + 'Test.png', true_label_test_image,  cmap = 'plasma')
matplotlib.image.imsave(labels_directory + 'Predicted.png', p_l, cmap = 'plasma')

train_matfile = {'train_image':tr_for_plot}
scipy.io.savemat(labels_directory + 'train_matfile.mat', train_matfile)

if super_pix_based:
  sgn_matfile = {'sgn':s_l}
  scipy.io.savemat(labels_directory + 'sgn_matfile.mat', sgn_matfile)


time_elapsed = (time.process_time() - start)
minutes, seconds = divmod(time_elapsed, 60)
print("Time elapsed is ", minutes, " minutes and ", seconds, " seconds." )



f = open(labels_directory + "accuracy.txt", "w")
f.write("Confusion Matrix\n")
f.write(np.array2string(confusion, separator=', '))
f.write("\nKappa: %.2f\n" % (cohen_kappa_score(true_labels_test, pred_labels_test)))
f.write("\nAccuracy: %.4f\n" % (accuracy_score(true_labels_test, pred_labels_test)))
f.write("Time elapsed is %.2f  minutes and %.2f seconds." % (minutes, seconds))
f.close()