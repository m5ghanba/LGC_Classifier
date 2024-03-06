# LGC Classifier
Local and Global Consistency Classifier Applied on Complex Compact Polarimetric (CP) and (Quad Polarimetric) Synthetic Aperture Radar (SAR) Data. This repository relates to the paper: Ghanbari, M., Xu, L., Clausi, D., A. (2023, Published). "Local and Global Spatial Information for Land Cover Semi-Supervised Classification of Complex Polarimetric SAR Data". IEEE Journal of Selected Topics in Applied Earth Observations and Remote Sensing.
# The Case with Complex CP SAR Data
Run the file LGC_Classifier_CP.py. It is assumed that the user has copied four files in the same directory as this file: 
1. The oversegmentation file named irgs_to_slic.mat. A MATLAB 2D array with the size of HxW (height and width of the data) that contains an oversegmentated regions with labels from 1 to n_seg, where n_seg is the total number of segments. 
2. The label files named labels.csv (the class labels are from 1 to NUM_CLASSES). 
3. The feature file: either SV.tif or feats.mat or feats.tif
4. labels_test.csv containing the test data.
Complete info about how these files are structured and obtained is found in the code LGC_Classifier_CP.py.

# The Case with Complex QP SAR Data
Run the file LGC_Classifier_fullQP.py.

# Comparison of the method with SVM and RF
Run the file RandomForrest_SupportVectorMachine.py.
