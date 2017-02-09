# cvlc rtsp://admin:admin@192.168.1.106/11 --video-filter=scene --scene-prefix=$(date +"%Y%m%d%H%M") --scene-format=jpg --scene-path=./ --scene-ratio 800 --sout-x264-lookahead=10 --sout-x264-tune=stillimage --vout=dummy --run-time 60 vlc://quit

import pickle
import pandas as pd
from sklearn.neighbors import KNeighborsClassifier
from sklearn.decomposition import PCA
try:
    from PIL import Image
except:
    import Image
import os
import glob
import numpy as np


STANDARD_SIZE = (300, 200)
N_COMPONENTS = 2
img_dir_0 = "/home/dahoiv/cam/stovsuger_0"
img_dir_1 = "/home/dahoiv/cam/stovsuger_1"

file_open = lambda x,y: glob.glob(os.path.join(x,y))

def matrix_image(image):
    "opens image and converts it to a m*n matrix" 
    image = Image.open(image)
    w, h = image.size
    crop = 300
    image.crop((0, crop, w, h-crop))
    image = image.resize(STANDARD_SIZE)
    
    image = list(image.getdata())
    image = np.array(image)
    return image

def flatten_image(image):  
    """
    takes in a n*m numpy array and flattens it to 
    an array of the size (1,m*n)
    """
    s = image.shape[0] * image.shape[1]
    image_wide = image.reshape(1,s)
    return image_wide[0]

if __name__ == "__main__":

    images = file_open(img_dir_0,"*.jpg")
    labels = ["0" for f in images]
    images2 = file_open(img_dir_1,"*.jpg")
    print(len(images), len(images2))
    images.extend(images2)
    labels.extend(["1" for f in images2])

    data = np.array([flatten_image(matrix_image(image)) for image in images])
    y = np.where(np.array(labels)=="1", 1, 0)

    is_train = np.random.uniform(0, 1, len(data)) <= 0.7
    train_x, train_y = data[is_train], y[is_train]
    test_x, test_y = data[is_train==False], y[is_train==False]

    if False:
        import matplotlib.pyplot as plt
        pca = PCA(n_components = 2, svd_solver='randomized', whiten=True).fit(data)
        X = pca.fit_transform(data)
        df = pd.DataFrame({"x": X[:, 0], "y": X[:, 1], "label":np.where(y==1, "Stovsuger", "Ikke Stovsuger")})
        colors = ["red", "yellow"]
        for label, color in zip(df['label'].unique(), colors):
            mask = df['label']==label
            plt.scatter(df[mask]['x'], df[mask]['y'], c=color, label=label)
        plt.legend()
        plt.show()

    pca = PCA(n_components = N_COMPONENTS, svd_solver='randomized', whiten=True)
    train_x = pca.fit_transform(train_x)
    knn = KNeighborsClassifier()
    knn.fit(train_x, train_y)

    with open('pca.pkl', 'wb') as f:
      pickle.dump(pca, f)
    with open('knn.pkl', 'wb') as f:
      pickle.dump(knn, f)

    test_x = pca.transform(test_x)
    print(pd.crosstab(test_y, knn.predict(test_x), rownames=["Actual"], colnames =["Predicted"]))
