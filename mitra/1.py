from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose

with ReachyMini() as mini:              # auto-connects to the sim daemon on localhost
    # "nod" — what robot.head.nod() wraps
    mini.goto_target(head=create_head_pose(z=20, roll=10, mm=True, degrees=True), duration=0.5)
    mini.goto_target(head=create_head_pose(), duration=0.5)

    # "capture_image" — frame of the MuJoCo scene, numpy (H, W, 3) uint8
    frame = mini.media.get_frame()
    print("camera frame:", frame.shape, frame.dtype)