# LCG Classifier: Classification Based on Local and Global Consistency   --Mohsen Ghanbari Spring 2020
# This program assumes the user copies four files in the same directory as this file:
# 1. The oversegmentation file named irgs_to_slic.mat
# 2. The label files named labels.csv (the class labels are from 1 to NUM_CLASSES)
# 3. The feature file: either SV.tif or feats.mat or feats.tif
# 4. labels_test.csv containing the test data
# Please follow the instruction in the program to set up these files and also to set the parameters (Make sure to set
# the number of classes).

import time
import numpy as np
start = time.process_time()



from skimage import io, data, segmentation, filters, color
from skimage.future import graph
import scipy.io
import matplotlib.pyplot as plt
import tifffile as tiff
import matplotlib
from sklearn.metrics import confusion_matrix, cohen_kappa_score, accuracy_score
import statistics
from scipy import stats as st
from tkinter.filedialog import askdirectory



def euclidean_norm_distance_metric(m_sp_i, m_sp_j):
  dis = np.sum(np.power(m_sp_i - m_sp_j, 2))
  return dis

# Calculates the maximum value of A\B and B\A where A and B are hermitian positive semidefinite CP coherence matrices, or simply, complex CP data
def max_HLT_distance_metric(m_sp_i, m_sp_j):
  coh1 = np.zeros((2, 2), dtype=complex)
  coh2 = np.zeros((2, 2), dtype=complex)

  coh1_r = np.array([[m_sp_i[0], m_sp_i[1]], [m_sp_i[1], m_sp_i[2]]])
  coh1_im = np.array([[0, m_sp_i[3]], [-m_sp_i[3], 0]])
  coh1 = coh1_r + (coh1_im * 1j)

  coh2_r = np.array([[m_sp_j[0], m_sp_j[1]], [m_sp_j[1], m_sp_j[2]]])
  coh2_im = np.array([[0, m_sp_j[3]], [-m_sp_j[3], 0]])
  coh2 = coh2_r + (coh2_im * 1j)

  hlt1 = np.real(np.trace(np.matmul(np.linalg.inv(coh1), coh2)))
  hlt2 = np.real(np.trace(np.matmul(np.linalg.inv(coh2), coh1)))

  return max(hlt1, hlt2)




# The folder that contains the train data: lables.csv. The program assumes the other files are in the current directory,
# meaning the directory of the current python file LGC_Classifier_V2.py
labels_directory = askdirectory(title='Select Folder That Contains the label file, labels.csv')
labels_directory = labels_directory + "/"



#OVERSEGMENTATION FILE
matfile = scipy.io.loadmat('irgs_to_slic.mat')# This mat file contains the oversegemntation image that is obtained through
# CP-IRGS. After segmenting the image with a certain number of classes (e.g., 50 classes), we need to label each region
# with an exclusive label. This is done by the Matlab script that I wrote named Labeling_each_segments_in_segmentation_differently.m
# One important thing is that you need to mask the land areas. Land areas are labeled to a really big number (10^7)
# in the segmentation image.
myImage = matfile['irgs_to_slic']
del matfile



#PARAMETER SETTING
complex_cp_only = True  #Whether the used features are only the coherence matrix elements or all the cp derived ones
is_there_normalization = False  #Whether the features should be normalized
#Parameters: SIGMA_S, SIGMA_L, BETA, K_NN (Please refer to the paper: Sellars et.al., 2019, "Super-pixel
# Contrcted Graph-based Learning For Hyperspectral Image Classification)
WEIGHT_SCALAR = 10  # The scalar in the wetghts in the calculation of S_i_w. The greater, the bigger the weights.
SIGMA_S = 1  # the sigma value in the RBF kernel related to S_i_m and S_i_w (The greater, the bigger the parameter s.)
SIGMA_L = 1000 # This should be a fairly large number since the Euclidean distance between the coordinates is mostly big
BETA = .9  # the greater the more effect from S_i_m rather than S_i_w
K_NN = 8 # the number of nearest neighbor, in case only_k_nearest is True.
only_k_nearest = False  # The boolean that specifies if we are only considering the k-NN. When False, we will have a full spatial correlation effect.
NUM_CLASSES = 4 # 1: OW/NI, 2: YI, 3: FYI, and 4: MYI (The user should put the number of classes.)
sea_ice_classification = False # This indicates the task is whether sea-ice classification (for which labels are
# collected by MAGIC) or a general classification for which the labels are collected by my code:
# labeled_data_collector_inserting_row_and_column_manually.py.
#The program assumes the user has put a csv file named labels.csv in the same directory as this python file.
# In the csv file exported from MAGIC. The labels are in the first column: 15, 1, 3, 6, 12 represent OW, NI, YI, FYI,
# and MYI, repectively. The second and third columns are column number and row number in the image.
# However, the labels are from 1 to l in the csv file generated by the upper-mentioned python script, with l being the
# number of classes
MIU = .1 # weighting in the LGC classifier
Cluste_based_testing = True # In case, the user wants their sample units to be squares around test pixels. Each test
# sample unit will be a square of "3 by 3" sqauare where the center pixel is each of the collected test pixels in the csv
# file. Therefore, choose True if you are sure all the pixels around each of the collected test pixels have the same
# labels as that of the collected test pixel.


#CONSTRUCTING A RAG
img = myImage
labels = myImage# An alternative way of obtaining the file labels: labels = segmentation.slic(img)
edge_map = filters.sobel(color.rgb2gray(img))# check
rag = graph.rag_boundary(labels, edge_map)

del edge_map

lc = graph.show_rag(labels, rag, img)
cbar = plt.colorbar(lc)
io.show()

del img



#MASKING OUT AREAS NOT TO BE PROCESSED
# Assuming the feature set has a size equal to img.shape[0] * img.shape[1] * n_feats where n_feats is the number of features
# that we are using in the classification. So as input, along with the oversegmentation (that contains land areas with label of 10^7),
# we need to ingest the file that contains the features. Here, this file is called "feats". Btw, do not forget to ingest
# the labeled data as well.

there_is_land = np.any(myImage == 10000000)

del myImage

if there_is_land:
  num_sup_pixels = len(rag) - 1 # number of superpixels is len(rag) - 1 (excluding land areas)
else:
  num_sup_pixels = len(rag) # number of superpixels



#FEATURE SETUP
if complex_cp_only:
  # mat_feat_file = scipy.io.loadmat('feats.mat')
  # feats = mat_feat_file['imag']
  #num_feats = feats.shape[2]

  Stokes_vec = tiff.imread('SV.tif')
  # Stokes_vec = feats[:, :, 17:21]
  coh_elements = np.zeros((Stokes_vec.shape[0],Stokes_vec.shape[1], 4))# c11, c12_real, c22, c12_imag

  coh_elements[:, :, 0] = 0.5 * (Stokes_vec[:, :, 0] + Stokes_vec[:, :, 1])
  coh_elements[:, :, 1] = 0.5 * Stokes_vec[:, :, 2]
  coh_elements[:, :, 2] = 0.5 * (Stokes_vec[:, :, 0] - Stokes_vec[:, :, 1])
  coh_elements[:, :, 3] = -0.5 * Stokes_vec[:, :, 3]

  #del Stokes_vec
  feats = coh_elements
  del coh_elements
  num_feats = feats.shape[2]
else:
  # Stokes_vec = tiff.imread('SV.tif')
  # # # Stokes_vec = feats[:, :, 17:21]
  # coh_elements = np.zeros((Stokes_vec.shape[0], Stokes_vec.shape[1], 4))  # c11, c12_real, c22, c12_imag
  #
  # coh_elements[:, :, 0] = 0.5 * (Stokes_vec[:, :, 0] + Stokes_vec[:, :, 1])
  # coh_elements[:, :, 1] = 0.5 * Stokes_vec[:, :, 2]
  # coh_elements[:, :, 2] = 0.5 * (Stokes_vec[:, :, 0] - Stokes_vec[:, :, 1])
  # coh_elements[:, :, 3] = -0.5 * Stokes_vec[:, :, 3]
  #
  # del Stokes_vec
  # feats = coh_elements
  # del coh_elements
  # feats = feats[:,:,[0,2]]

  # mat_feat_file = scipy.io.loadmat('feats.mat')
  # feats = mat_feat_file['imag']



  feats = tiff.imread('feats.tif')
  num_feats = feats.shape[2]



#NORMALIZATION
if is_there_normalization:
  for feat in range(0, num_feats):
    min_f = np.min(feats[:, :, feat])
    max_f = np.max(feats[:, :, feat])
    feats[:, :, feat] = (feats[:, :, feat] - min_f) / (max_f - min_f)



#CALCULATE OTHER FEATURES TO SET UP AFFINITY MATRIX, W. THESE FEATURES INCLUDE S_i_p, S_i_m, S_i_w.
# Calculate S_i_m and S_i_p each with the size of num_sup_pixels*n_feats. This matrix consists of the mean feature values
# and the mean x and y coordinates of all the superpixels.
S_i_p = np.zeros((num_sup_pixels, 2), dtype=int)
S_i_m = np.zeros((num_sup_pixels, num_feats))
for num_sp in range(0, num_sup_pixels):  # the labels of superpixels are in range [0, num_sup_pixels)
  idxs = np.where(labels == num_sp)  # gives us a tuple-typed output of rows and columns idxs[0]-->rows
  S_i_p[num_sp, 0] = np.mean(idxs[0])  # mean of rows
  S_i_p[num_sp, 1] = np.mean(idxs[1])  # mean of cols

  S_i_m[num_sp, :] = np.mean(feats[idxs], axis=0)  # mean of feats

S_i_w = np.zeros((num_sup_pixels, num_feats))
for num_sp in rag:
  num_of_neighbors = len(rag[num_sp])
  # l_num_sp = list(rag.adj.keys())[num_sp] # the label of current sp
  if num_sp >= num_sup_pixels: # current sp is representing land areas
    continue
  ls_neighbours_idxs = sorted(rag.adj[num_sp].keys()) # the label of neighbours of the current sp
  if any(neighbor_labels >= num_sup_pixels for neighbor_labels in ls_neighbours_idxs): #one of the neighbors (the last one) is land
    num_of_neighbors -= 1

  w_i_zj = np.zeros((num_of_neighbors, 1))
  sum_w = 0

  for num_neighbors in range (0, num_of_neighbors):
    if complex_cp_only:
      w_i_zj[num_neighbors, 0] = np.exp(- max_HLT_distance_metric(S_i_m[num_sp, :],
                                            S_i_m[ls_neighbours_idxs[num_neighbors], :]) / WEIGHT_SCALAR)
      sum_w += np.exp(- max_HLT_distance_metric(S_i_m[num_sp, :],
                                                       S_i_m[ls_neighbours_idxs[num_neighbors], :]) / WEIGHT_SCALAR)
    else:
      w_i_zj[num_neighbors, 0] = np.exp(- euclidean_norm_distance_metric(S_i_m[num_sp, :],
                                            S_i_m[ls_neighbours_idxs[num_neighbors], :]) / WEIGHT_SCALAR)
      sum_w += np.exp(- euclidean_norm_distance_metric(S_i_m[num_sp, :],
                                                       S_i_m[ls_neighbours_idxs[num_neighbors], :]) / WEIGHT_SCALAR)
  w_i_zj = w_i_zj / sum_w

  for num_neighbors in range(0, num_of_neighbors):
    S_i_w[num_sp, :] += w_i_zj[num_neighbors, 0] * S_i_m[ls_neighbours_idxs[num_neighbors], :]



#CALCULATING W
# W has a size of num_sup_pixels*num_sup_pixels and the element ij, for example, in the matrix represents the weight between the
# regions (superpixels) that have labels i and j.
W = np.zeros((num_sup_pixels, num_sup_pixels))

if only_k_nearest:
  dist = np.zeros((num_sup_pixels, num_sup_pixels))  # This matrix is the eudlidean distance values between superpixels
  for num_sp_r in range(0, num_sup_pixels):
    for num_sp_c in range(num_sp_r + 1, num_sup_pixels):
      dist[num_sp_r, num_sp_c] = euclidean_norm_distance_metric(S_i_p[num_sp_r, :], S_i_p[num_sp_c, :])
  dist += np.transpose(dist)  # The matrix dist is symmetric. This line is to make the lower triangle the same as the upper one.

  arg_sort_dist = np.argsort(dist, axis=1)

  for num_sp_r in range(0, num_sup_pixels):
    for sort_num_sp_c in range(1, K_NN + 1):  # the k nearest neighbour. First one is the superpixel itself.
      num_sp_c = arg_sort_dist[num_sp_r, sort_num_sp_c]
      if complex_cp_only:
        s = np.exp(((BETA - 1) * max_HLT_distance_metric(S_i_w[num_sp_r, :], S_i_w[num_sp_c, :]))
                   - (BETA * max_HLT_distance_metric(S_i_m[num_sp_r, :], S_i_m[num_sp_c, :])) /
                                                                                             (2 * np.power(SIGMA_S, 2)))
        l = np.exp(-euclidean_norm_distance_metric(S_i_p[num_sp_r, :], S_i_p[num_sp_c, :]) / (2 * np.power(SIGMA_L, 2)))
      else:
        s = np.exp(((BETA - 1) * euclidean_norm_distance_metric(S_i_w[num_sp_r, :], S_i_w[num_sp_c, :]))
                   - (BETA * euclidean_norm_distance_metric(S_i_m[num_sp_r, :], S_i_m[num_sp_c, :])) /
                                                                                             (2 * np.power(SIGMA_S, 2)))
        l = np.exp(-euclidean_norm_distance_metric(S_i_p[num_sp_r, :], S_i_p[num_sp_c, :]) / (2 * np.power(SIGMA_L, 2)))
      W[num_sp_r, num_sp_c] = s * l
  del arg_sort_dist

else:  # full spatial correlation effect
  for num_sp_r in range(0, num_sup_pixels):
    for num_sp_c in range(num_sp_r + 1, num_sup_pixels):
      if complex_cp_only:
        s = np.exp(((BETA - 1) * max_HLT_distance_metric(S_i_w[num_sp_r, :], S_i_w[num_sp_c, :]))
                   - (BETA * max_HLT_distance_metric(S_i_m[num_sp_r, :], S_i_m[num_sp_c, :])) /
                                                                                             (2 * np.power(SIGMA_S, 2)))
        l = np.exp(-euclidean_norm_distance_metric(S_i_p[num_sp_r, :], S_i_p[num_sp_c, :]) / (2 * np.power(SIGMA_L, 2)))
      else:
        s = np.exp(((BETA - 1) * euclidean_norm_distance_metric(S_i_w[num_sp_r, :], S_i_w[num_sp_c, :]))
                   - (BETA * euclidean_norm_distance_metric(S_i_m[num_sp_r, :], S_i_m[num_sp_c, :])) /
                                                                                             (2 * np.power(SIGMA_S, 2)))
        l = np.exp(-euclidean_norm_distance_metric(S_i_p[num_sp_r, :], S_i_p[num_sp_c, :]) / (2 * np.power(SIGMA_L, 2)))
      W[num_sp_r, num_sp_c] = s * l
  W += np.transpose(W)  # The matrix W is symmetric; this line is to make the lower triangle the same as the upper one.

# del S_i_m, S_i_p, S_i_w, rag, w_i_zj



#CONSTRUCTING THE MATRIX D
# Matrix D is the same size as W. The matrix D is a diagonal matrix with the i,i element equal to the sum of i-th row of W
D = np.zeros((num_sup_pixels, num_sup_pixels))
w_sum = np.sum(W, axis = 1)
for num_sp in range (0, num_sup_pixels):
  D[num_sp, num_sp] = w_sum[num_sp]



# INITIAL LABEL MATRIX Y

csv_file = np.genfromtxt(labels_directory + 'labels.csv', dtype = 'int', delimiter=',')
if sea_ice_classification is False:
  NUM_CLASSES = np.max(csv_file[:, 0])

# Matrix Y which is the label file: Y has a size of num_sup_pixels*NUM_CLASSES.
Y = np.zeros((num_sup_pixels , NUM_CLASSES))

# Here, we assign the same label to the containing superpixel as that of each of the labeled pixels
y_for_plot = np.zeros(labels.shape) #(NUM_CLASSES + 1) * np.ones(labels.shape)


if sea_ice_classification:
  for num_labelled in range (0, csv_file.shape[0]): # It just assigns the label of last pixel to the superpixel.
    if csv_file[num_labelled, 0] == -1: # The pixel is unlabeled. MAGIC gives -1 when you skip the pixel.
      continue


    sp = labels[csv_file[num_labelled, 2] - 1, csv_file[num_labelled, 1] - 1] # to get the superpixel number that contains the current labeled pixel

    if sp > num_sup_pixels: # land areas
      continue

    if NUM_CLASSES == 4:
      if csv_file[num_labelled, 0] == 15:  # OW
        Y[sp, 0] = 1
      elif csv_file[num_labelled, 0] == 1:  # NI
        Y[sp, 0] = 1
      elif csv_file[num_labelled, 0] == 3:  # YI
        Y[sp, 1] = 1
      elif csv_file[num_labelled, 0] == 6:  # FYI
        Y[sp, 2] = 1
      elif csv_file[num_labelled, 0] == 12:  # MYI
        Y[sp, 3] = 1
    elif NUM_CLASSES == 3:  # no OW/NI
      if csv_file[num_labelled, 0] == 3:  # YI
        Y[sp, 0] = 1
      elif csv_file[num_labelled, 0] == 6:  # FYI
        Y[sp, 1] = 1
      elif csv_file[num_labelled, 0] == 12:  # MYI
        Y[sp, 2] = 1


else: # general classification where labels in the csv file starts from 1 to NUM_CLASSES.
  for num_labelled in range(0, csv_file.shape[0]):
    #row = int((csv_file[num_labelled, 2] - 1) * labels.shape[0] / 19227)
    #col = int((csv_file[num_labelled, 1] - 1) * labels.shape[1] / 2710)
    row = csv_file[num_labelled, 2] - 1
    col = csv_file[num_labelled, 1] - 1
    sp = labels[row, col]  # to get the superpixel number that contains the current labeled pixel

    if sp > num_sup_pixels:  # mask areas
      continue


    Y[sp, :] = 0
    Y[sp, csv_file[num_labelled, 0] - 1] = 1

for num_sp in range(0, num_sup_pixels):
  if any(i == 1 for i in Y[num_sp, :]):
    for cl in range (1, NUM_CLASSES + 1):
      if (Y[num_sp, cl-1] == 1):
        y_for_plot[np.where(labels == num_sp)] = cl



# CALCULATING F
# The matrix F (soft labels) is sized num_sup_pixels*num_labels.

beta_f = MIU / (MIU + 1)
alfa_f = 1 - beta_f

s_f = np.matmul( np.matmul( np.linalg.inv(np.sqrt(D)) , W) , np.linalg.inv(np.sqrt(D)))# matrix S in LGC
F = beta_f * np.matmul( np.linalg.inv(np.identity(num_sup_pixels) - alfa_f * s_f) , Y )



# LABEL PREDICTION
predicted_labels = np.empty_like(labels)
predicted_labels[:] =  labels
F_sorted = np.argsort(F, axis = 1)
for num_sp in range (0, num_sup_pixels):
  predicted_labels[np.where(labels == num_sp)] = F_sorted[num_sp, NUM_CLASSES - 1] + 1



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
for n_c in range(0, confusion[0].size):
  u_a = confusion[n_c, n_c] / np.sum(confusion[n_c, :])
  print('\nUser Accuracy: class {:.2f}{:.2f}\n'.format(n_c + 1, u_a))
print('Confusion Matrix\n')
print(confusion)
print('\nKappa: {:.2f}\n'.format(cohen_kappa_score(true_labels_test, pred_labels_test)))
print('\nAccuracy: {:.2f}\n'.format(accuracy_score(true_labels_test, pred_labels_test)))



#PLOT RESULTS
p_l = np.empty_like(predicted_labels)
p_l[:] =  predicted_labels
p_l[np.where(predicted_labels==10000000)] = NUM_CLASSES + 1 # forcing the land areas to have label 5.

s_l = np.empty_like(labels)
s_l[:] =  labels
s_l[np.where(labels==10000000)] = num_sup_pixels + 1 # forcing the land areas to have a label not too far from other labels.


# from matplotlib.colors import ListedColormap
# C = [[77/255,191/255,237/255], [0, 0, 1], [0, 1, 0], [1, 0, 0], [250/255, 250/255, 13/255]]
# cm = ListedColormap(C)

#custom colormap used for train image
cmap = matplotlib.colors.ListedColormap([(1, 1,1), (12 / 255, 7 / 255, 134 / 255), (155 / 255, 23 / 255, 158 / 255),
                           (236 / 255, 120 / 255, 83 / 255), (239 / 255, 248 / 255, 33 / 255)], name='colors', N=None)


fig = plt.figure()
ax1 = fig.add_subplot(131)
ax2 = fig.add_subplot(132)
ax3 = fig.add_subplot(133)
ax1.set_title('Segmentation')
ax1.imshow(s_l)
ax2.set_title('Train')
ax2.imshow(y_for_plot,  cmap=cmap)
# leg2 = ax2.legend();
ax3.set_title('Predicted')
ax3.imshow(p_l, cmap='plasma')
# leg3 = ax3.legend()
plt.show()



#SAVE RESULTS
matplotlib.image.imsave(labels_directory + 'Segmentation.png', s_l)
matplotlib.image.imsave(labels_directory + 'Train.png', y_for_plot,  cmap = cmap)
matplotlib.image.imsave(labels_directory + 'Test.png', true_label_test_image,  cmap = cmap)
matplotlib.image.imsave(labels_directory + 'Predicted.png', p_l, cmap = 'plasma')


time_elapsed = (time.process_time() - start)
minutes, seconds = divmod(time_elapsed, 60)
print("Time elapsed is ", minutes, " minutes and ", seconds, " seconds." )



f = open(labels_directory + "accuracy.txt", "w")
f.write("Confusion Matrix\n")
for n_c in range(0, confusion[0].size):
  u_a = confusion[n_c, n_c] / np.sum(confusion[n_c, :])
  f.write("\nUser Accuracy: class %.4f %.4f\n" % (n_c + 1, u_a))
f.write(np.array2string(confusion, separator=', '))
f.write("\nKappa: %.2f\n" % (cohen_kappa_score(true_labels_test, pred_labels_test)))
f.write("\nAccuracy: %.4f\n" % (accuracy_score(true_labels_test, pred_labels_test)))
f.write("Time elapsed is %.2f  minutes and %.2f seconds." % (minutes, seconds))
f.close()
# globals().clear()
#
data_gcns = {'W':W,'S_i_m':S_i_m,'Y':Y, 'labels':labels}
scipy.io.savemat(labels_directory + 'Data_exported.mat', data_gcns)

labeled_map = {'predicted_labels':predicted_labels}
scipy.io.savemat(labels_directory + 'result.mat', labeled_map)