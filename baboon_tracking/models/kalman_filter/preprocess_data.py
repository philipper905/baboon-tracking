from baseline_model import *
from pathlib import Path 
import numpy as np
import pandas as pd
import os
import math
import pickle
import matplotlib.pyplot as plt
from tensorboardX import SummaryWriter
from datetime import date


root = Path('../../..')

config = {}
config['k_nearest_baboons'] = 4 #getting the four nearest baboons per frame to consider(MUST BE EVEN)
config['k_historic_velocities'] = 4 #getting the four past velocities to consider
config['checkpoint_training'] = False
config['saved_path'] = 'saved_weights.pth' #path to save current model information (epoch, weights, etc...)
config['learning_rate'] = 0.0001 #lr
config['batch_size'] = 32 # Number of training samples per batch to be passed to network
config['val_split'] = 0.2 #ratio of val and training data
config['shuffle_dataset'] = True #shuffle data before start (TODO: change this if we use kfold?)
config['epochs'] = 100  # Number of epochs to train the model
config['early_stop'] = True  # Implement early stopping or not
config['early_stop_epoch'] = 3 # Number of epochs for which validation loss increases to be counted as overfitting
config['input_training_data'] = root / 'ml_data' / 'DJI_0769_1st_2250_frames.csv'
config['data_output_path'] = './data.npy'
config['labels_output_path'] = './labels.npy'


#DO NOT CHANGE THE FOLLOWING 
config['input_dimension'] = config['k_nearest_baboons'] + config['k_historic_velocities'] + 1 #DON'T TOUCH THIS
config['validation_loss_path'] = '' #leave empty 
config['training_loss_path'] = '' #leave empty 
config['output_dimension'] = 1 #leave empty

#config checks
assert( config['k_nearest_baboons'] % 2 == 0 )
assert( os.path.isfile(config['input_training_data']) == True)



# This is assuming the obvious assumption that a baboon only has one position per frame
#TODO : Assuming data is ordered by frame (increasing timesteps/frames)
training_data = pd.read_csv(config['input_training_data'])

frames_to_velocities = {} #Maps a single frame to a list of all the baboons, their id, position, and velocity

for idx, row in training_data.iterrows():
    current_frame = row.loc['frame']
    current_position = (row.loc['centroid_x'], row.loc['centroid_y'])
    current_velocity = row.loc['velocity']
    current_id = row.loc['baboon id']
    
    if current_frame not in frames_to_velocities:
        frames_to_velocities[current_frame] = []
    
    frames_to_velocities[current_frame].append((current_position, current_velocity, current_id))

"""
Returns the K physically nearest baboons to baboon_id at the given frame

Pre-pends with negative ones if there are less than k nearest baboons in the frame
"""
def get_k_nearest_baboons_velocities(frame, baboon_id):
    baboons_in_frame = frames_to_velocities[frame].copy()
    output = []
    
    target_position = (-1, -1)
    
    #get rid of the baboon we are considering
    for idx, baboon in enumerate(baboons_in_frame):
        if baboon[2] == baboon_id:
            target_velocity = baboons_in_frame[idx][0]
            del baboons_in_frame[idx]
            break
      
    if len(baboons_in_frame) <= config['k_nearest_baboons']:
        padded_output = list(np.ones(config['k_nearest_baboons'] - len(baboons_in_frame)) * -1)
        return padded_output.extend([item[1] for item in baboons_in_frame])
    
    for k_nearest_neighbor in range(config['k_nearest_baboons']):
        min_distance = math.inf
        min_velocity = -1
        min_idx = -1
        
        for idx, baboon in enumerate(baboons_in_frame):
            current_distance = np.linalg.norm(np.array(baboon[0]) - np.array(target_velocity))
            if current_distance < min_distance:
                min_distance = current_distance
                min_velocity = baboon[1]
                min_idx = idx
        
        output.append(min_velocity)
        del baboons_in_frame[min_idx]
        
    return output
            

#TODO : Must check for 'extended' periods of discountinuous frames for future potentially sparese labeled data
#TODO : Assuming data is ordered by frame (increasing timesteps/frames)
#TODO : Warning : if there are not enough K historic frames then we pre pad with negative ones

baboons_to_velocities = {} #maps the baboon's id to it's velocties and respective frames in a tuple

for idx, row in training_data.iterrows():
    current_frame = row.loc['frame']
    current_position = (row.loc['centroid_x'], row.loc['centroid_y'])
    current_velocity = row.loc['velocity']
    current_id = row.loc['baboon id']
    
    if current_id not in baboons_to_velocities:
        baboons_to_velocities[current_id] = []
        
    baboons_to_velocities[current_id].append((current_velocity, current_frame))

"""
Given a frame returns the k past velocities of the given baboon_id

Pre pads with negative ones if there are less than k previous frames available in the labeled data
"""
def get_k_past_velocities(current_frame, baboon_id):
    velocities = baboons_to_velocities[baboon_id]
    
    #annoying but I don't know how to do this easier
    frame_index = -1
    for idx, frame in enumerate(velocities):
        if frame[1] == current_frame:
            frame_index = idx
            break
            
    if frame_index == -1:
        raise RuntimeError('Frame does not exist in dataset for this baboon_id')
        
    if frame_index < config['k_historic_velocities']:
        padded_output = list(np.ones(config['k_historic_velocities'] - frame_index) * -1)   
        padded_output.extend([item[0] for item in velocities[:frame_index]])
        return padded_output
    
    else:
        return [item[0] for item in velocities[frame_index-config['k_historic_velocities'] : frame_index]]


print('labeling data')
training_data = pd.read_csv(config['input_training_data'])
X = []
labels = []

start_historic = 1 + config['k_nearest_baboons']

for idx, row in training_data.iterrows():
    print(f'Labeling Row  {idx}/{len(training_data)}')
    current_frame = row.loc['frame']
    current_position = (row.loc['centroid_x'], row.loc['centroid_y'])
    current_velocity = row.loc['velocity']
    current_id = row.loc['baboon id']
    
    current_label = training_data.loc[(training_data['frame'] == (current_frame + 1)) & (training_data['baboon id'] == current_id)]
    if(current_label.empty):
        #last frame for baboon, therefore no label
        continue
        
    #create the label
    current_label_velocity = current_label['velocity'].to_numpy()

    #create the datapoint
    current_datapoint = np.zeros(config['input_dimension'])
    current_datapoint[0] = current_velocity
    current_datapoint[1:start_historic] = get_k_nearest_baboons_velocities(current_frame, current_id)
    current_datapoint[start_historic:] = get_k_past_velocities(current_frame, current_id)
    
    X.append(current_datapoint)
    labels.append(current_label_velocity)

X = np.array(X)
labels = np.array(labels)

np.save(config['data_output_path'], X)
np.save(config['labels_output_path'], labels)