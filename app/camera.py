import os
import cv2
from picamera2 import Picamera2, Preview
import numpy as np
from picamera2.encoders import H264Encoder
import time
import datetime
import threading

from . import db
from .models import Recording
from flask import current_app,Flask

class Camera:
    def __init__(self,app : Flask):
        self.app = app  # Pass the Flask app instance
        print("camera init")
        self.camera = Picamera2()
        # define lower resolution for processing saving
        lsize=(1080,720)
        lsize=(480,270)
        # configure GPU to provide video feed
        #video_config = self.camera.create_video_configuration({"size": (1920, 1080)})
        # it seems that yuv420 is less processing consuming ( to be further investigated)
        video_config = self.camera.create_video_configuration(main={"size": (1920, 1080), "format": "YUV420"},lores={
                                                 "size": lsize, "format": "RGB888"})
        print(video_config)
        #config = picam2.create_still_configuration()
        self.camera.configure(video_config)
        #self.camera.configure(self.camera.create_preview_configuration(main={"format": "RGB888"}))
        # define an H264 encoder to stream or to store video
        self.encoder = H264Encoder(10000000)
        # Load the pre-trained Haar cascade classifier for face recognition
        # would be nice to investigate with dlib if we can improve processing
        self.face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
        self.camera.start()
        # define a rotation angle in case camera cannot be put on a stand and needs rotation
        self.angle = 0
        # improve battery usage only compute every n frames for face recognition
        # as we are running 30 frames per sec, using every 5 frames is about 160 ms
        self.process_every_n_frames = 3
        self.frame_count = 0
        # as the goal is to check door opening we consider doing first a simple motion detection
        # and in case door is open we check for a face detection
        self.current_frame = None
        self.reference_frame = None # as named a reference form to compare from
        self.previous_faces = []
        self.frames_since_last_detection = 0
        self.frames_to_remember_faces = 10 # this is used for gui such the frame around faces stays longer
        # just for info and show msg on video feed for motion detection
        self.motion_detected = False
        # recording of video clip
        self.recording = False
        self.video_writer = None
        self.recording_filename = None
        self.processing_active = False
        self.capture_thread = threading.Thread(target=self.capture_and_process, daemon=True)
        self.capture_thread.start()
        
    def save_recording_metadata(self, filename):
        with self.app.app_context():
            new_recording = Recording(filename=filename, timestamp=datetime.datetime.now().replace(microsecond=0))
            db.session.add(new_recording)
            db.session.commit()

    def start_recording(self, frame_size):
        fourcc = cv2.VideoWriter_fourcc(*'X264')
        self.recording_filename = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".mp4"
        recording_path = os.path.join( 'recordings', self.recording_filename)
        #recording_path = os.path.join(self.app.static_folder, 'recordings', self.recording_filename)
        self.video_writer = cv2.VideoWriter(recording_path, fourcc, 20.0, frame_size)

        #self.video_writer = cv2.VideoWriter(filename, fourcc, 20.0, frame_size)
        self.recording = True
        

    def stop_recording(self):
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None
        self.recording = False
        if self.recording_filename:
            self.save_recording_metadata(self.recording_filename)
            
        


    def detect_motion(self, frame):
        if self.reference_frame is None:
            self.reference_frame = frame
            return False

        # Compute the absolute difference between the current frame and reference frame
        frame_diff = cv2.absdiff(self.reference_frame, frame)
        gray_diff = cv2.cvtColor(frame_diff, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray_diff, 25, 255, cv2.THRESH_BINARY)
        motion_score = np.sum(thresh) / 255

        # Update the reference frame periodically
        self.reference_frame = frame

        # Consider motion detected if motion score is above a certain threshold
        return motion_score > 500  # Threshold value can be adjusted
    
    def capture_and_process(self):
        while True:
            rgb_frame = self.camera.capture_array("lores")
            if rgb_frame is not None:
                #rgb_frame = cv2.cvtColor(frame, cv2.COLOR_YUV420p2RGB)
                self.current_frame=rgb_frame
                #small_frame = cv2.resize(rgb_frame, (320, 240))
                if self.processing_active:
                    # resize frame to lower processing as full frame is not needed
                    #small_frame = cv2.resize(rgb_frame, (320, 240))
                    #self.motion_detected = self.detect_motion(small_frame)
                    self.motion_detected = self.detect_motion(rgb_frame)
                    if self.motion_detected:
                        # once motio is detected we search for a face
                        #gray = cv2.cvtColor(small_frame, cv2.COLOR_RGB2GRAY)
                        gray = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2GRAY)
                        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
                        if len(faces) > 0:
                            self.previous_faces = faces
                            self.frames_since_last_detection = 0
                            if not self.recording:
                                self.start_recording((rgb_frame.shape[1], rgb_frame.shape[0]))
                        else:
                            self.frames_since_last_detection += 1
                        if self.frames_since_last_detection > self.frames_to_remember_faces:
                            self.previous_faces = []
                            if self.recording:
                                self.stop_recording()
                    else:
                        if self.recording:
                            self.stop_recording()
                    if self.recording:
                        self.video_writer.write(rgb_frame)
            #time.sleep(1)   


    def get_frame_orig(self):
        # working but take a lot of cpu power
        #frame = self.camera.capture_array()
        frame = self.camera.capture_array("lores")
        faces=[]
        # not working
		#frame =self.camera.capture_buffer("lores")
        if frame is not None:
            # as most processing is computed in rgb
            rgb = cv2.cvtColor(frame, cv2.COLOR_YUV420p2RGB)
            # rotate frame in case off
            if self.angle != 0:
                
                
                (h, w) = rgb.shape[:2]
                center = (w // 2, h // 2)
                matrix = cv2.getRotationMatrix2D(center, self.angle, 1.0)
                frame = cv2.warpAffine(rgb, matrix, (w, h))
            # Reduce frame size for processing
            small_frame = cv2.resize(rgb, (540, 360))   
            #ret, jpeg = cv2.imencode('.jpg', frame)
            if self.detect_motion(small_frame):
                # Process every nth frame
                self.frame_count += 1
                if self.frame_count % self.process_every_n_frames == 0:
                    # Reduce frame size for processing
                    #small_frame = cv2.resize(rgb, (540, 360))
                    # Convert to grayscale for face detection
                    gray = cv2.cvtColor(small_frame, cv2.COLOR_RGB2GRAY)
                    faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
                if len(faces)>0:
                    
                    for (x, y, w, h) in faces:
                        x = int(x * (rgb.shape[1] / small_frame.shape[1]))
                        y = int(y * (rgb.shape[0] / small_frame.shape[0]))
                        w = int(w * (rgb.shape[1] / small_frame.shape[1]))
                        h = int(h * (rgb.shape[0] / small_frame.shape[0]))
                        cv2.rectangle(rgb, (x, y), (x + w, y + h), (255, 0, 0), 2)
                    cv2.putText(rgb, "Face detected", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    

                # Overlay "Motion Detected" text
                cv2.putText(rgb, "Motion Detected", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)


			
			
			# Draw rectangle around the faces
            #for (x, y, w, h) in faces:
            #    cv2.rectangle(rgb, (x, y), (x+w, y+h), (255, 0, 0), 2)
            
            
            ret, jpeg = cv2.imencode('.jpg', rgb)
            return jpeg.tobytes()
        else:
            return None
    def get_frame(self):
        #frame = self.camera.capture_array("lores")
        #rgb_frame = self.current_frame
        if self.current_frame is not None:
            #rgb_frame = cv2.cvtColor(frame, cv2.COLOR_YUV420p2RGB)
            for (x, y, w, h) in self.previous_faces:
                x = int(x * (self.current_frame.shape[1] / 320))
                y = int(y * (self.current_frame.shape[0] / 240))
                w = int(w * (self.current_frame.shape[1] / 320))
                h = int(h * (self.current_frame.shape[0] / 240))
                cv2.rectangle(self.current_frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
            if self.motion_detected:
                cv2.putText(self.current_frame, "Motion Detected", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            if self.angle != 0:
                (h, w) = self.current_frame.shape[:2]
                center = (w // 2, h // 2)
                matrix = cv2.getRotationMatrix2D(center, self.angle, 1.0)
                rgb_frame = cv2.warpAffine(self.current_frame, matrix, (w, h))
                self.current_frame=rgb_frame
            ret, jpeg = cv2.imencode('.jpg', self.current_frame)
            return jpeg.tobytes()
        else:
            return None
    def toggle_processing(self):
        self.processing_active = not self.processing_active
            
    def rotate(self, angle):
        self.angle = angle
    