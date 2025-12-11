import numpy as np

def encode_face(descriptor_list):
    """
    descriptor_list = [0.02, -0.11, ..., 0.33] length 128
    Store as numpy array for consistency.
    """
    arr = np.array(descriptor_list, dtype="float32")
    return arr

def face_distance(known_embedding, candidate_embedding):
    """Compute Euclidean distance between two 128-d vectors."""
    known = np.array(known_embedding, dtype="float32")
    cand = np.array(candidate_embedding, dtype="float32")
    return np.linalg.norm(known - cand)
