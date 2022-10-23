#!/usr/bin/env python3

import rospy
import cv2
from cv_bridge import CvBridge, CvBridgeError
import numpy as np

import message_filters

from following_person.msg import rect_msg
from sensor_msgs.msg import Image
from geometry_msgs.msg import Twist

from following_person.srv import target_srv

class driver():
    def __init__(self):
        self.target = 1
        self.missing_time =0

        self.pub = rospy.Publisher('cmd_vel',Twist,queue_size=20)
        self.bridge = CvBridge()

        self.position_sub = message_filters.Subscriber('tracking_data',rect_msg)
        self.depth_sub = message_filters.Subscriber('/zed2/zed_node/depth/depth_registered',Image)
        ts = message_filters.ApproximateTimeSynchronizer([self.position_sub, self.depth_sub], 20, 0.1, allow_headerless=True)
        ts.registerCallback(self.callback)
    
        rospy.spin()

    def callback(self,position_data,depth_data):
        cx = position_data.cx
        cy = position_data.cy
        id =position_data.label
      
        if id == self.target:
            if self.missing_time !=0:
                print('continue following ~')
                self.missing_time = 0
            linear_x = self.linear(cx,cy,depth_data)

            angular_z = self.angular(cx)

            self.publisher(linear_x, angular_z)

        elif id != self.target and self.missing_time <= 50:
            self.missing_time += 1
            if self.missing_time == 1:
                print('missing target...')

        else:
            self.missing_time = 0
            self.client()

        
        
    def linear(self,cx,cy,depth_data):

        try:
            depth_image = self.bridge.imgmsg_to_cv2(depth_data, '32FC1')
        except CvBridgeError as e:
            print(e)

        depth_array = np.array(depth_image, dtype=np.float32)
        # depth_array[np.isneginf(depth_array)] = 0.0
        # depth_array[np.isposinf(depth_array)] = 0.0
        depth_array = self.fill_depth_array(depth_array)

        dist = depth_array[cy,cx]

        speed = self.dist_to_speed(dist)

        return speed

    def fill_depth_array(self, depth_array):

        for i in range(depth_array.shape[1]):

            temp_col = depth_array[:,i]

            nan_num = np.count_nonzero(temp_col != temp_col)

            if nan_num != 0:

                temp_not_nan_col = temp_col[temp_col == temp_col]

                temp_col[np.isnan(temp_col)] = temp_not_nan_col.mean()

        return depth_array

    def dist_to_speed(self, dist):

        if dist == np.NINF:

            speed = 0.0

        elif dist  == np.inf or np.nan:

            speed = 0.3

        elif dist <= 0.22:
            
            speed = 0.0

        else:

            speed = (dist - 0.4) ** 0.5 / 2

        return speed

    def angular(self, cx):

        if cx == 320 :

            angle = 0.0

        elif cx > 320:
            angle = ((cx - 320) / 320) ** 0.5 / 2
            
        else:
            angle = -(((320 - cx) / 320) ** 0.5 / 2)

        return angle

    def publisher(self, linear_x, angular_z):

        msg = Twist()

        msg.linear.x = linear_x
        msg.angular.z = angular_z

        self.pub.publish(msg)

    def client(self):

        rospy.wait_for_service('change_target')

        try:
            new_id = int(input('Enter changing target:'))
            changing_target = rospy.ServiceProxy('change_target',target_srv, persistent=False)
            resp = changing_target(new_id)
            self.target = resp.new_id
            print('continue following with new taget: ',self.target)
            return resp.new_id

        except rospy.ServiceException as e:
            print('Service call failed: %s'%e)


if __name__ == '__main__':

    rospy.init_node('controller_node')

    car = driver()