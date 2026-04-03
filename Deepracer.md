# Deepracer setup



**MAKE SURE THE ROBOTS WHEELS ARE NOT TOUCHING THE GROUND DURING THIS PROCESS, IT MAY SUDDENLY START DRIVING FAST AND UNEXPECTEDLY AND DAMAGE ITSELF OR OTHER THINGS IN THE LAB**

1. Make sure both your laptop and the deepracer are connected to the NESTlab network

2. SSH into the deepracer with the following command 

```bash
ssh deepracer@192.168.1.103
```

```bash
ssh phobos@192.168.1.105
```

and start the robot ros nodes with

```bash
mars_start
```


3. On **your computer, not the ssh shell** run `pyenv shell 3.14.3` in the terminal you will be using so you have the right python version

4. To get the message list run the following command on said terminal


```bash
python3 fetch_ros_topics.py \
  --ros-version 2 \
  --output ros_topics.txt \
  --duration 5 \
  --ros-bridge-python /usr/bin/python3.8 \
  --ros-bridge-pythonpath /opt/ros/foxy/lib/python3.8/site-packages
```

Single-line equivalent (avoids line-continuation issues):

```bash
python3 fetch_ros_topics.py --ros-version 2 --output ros_topics.txt --duration 5 --ros-bridge-python /usr/bin/python3.8 --ros-bridge-pythonpath /opt/ros/foxy/lib/python3.8/site-packages
```

where duration is capture time in seconds (5 works well here), ros bridge python is the python enviornment to run from (this needs to be the same as ros2 foxy uses or the rclpy library won't work), and the python path is self explanitory

5. To execute mars code run the following in the same terminal

```bash
python3 main.py test_file.mars \
  --ros-autostart \
  --ros-version 2 \
  --ros-bridge-python /usr/bin/python3.8 \
  --ros-bridge-pythonpath /opt/ros/foxy/lib/python3.8/site-packages
```

All the variables are the same here as in step 4

Congrats you have now run mars code with the ros bridge, yippie

Here is an example program which drives forwards for 10 seconds then stops

```mars
int ticks = 0;
int drive_ticks = 10; #drive for 10sec 



while (ticks < drive_ticks) {
    publish("/cmd_vel", "geometry_msgs/msg/Twist", {
        "linear": {"x": 1.0, "y": 0.0, "z": 0.0},
        "angular": {"x": 0.0, "y": 0.0, "z": 0.0}
    });

    wait(1);

    ticks = ticks + 1;
    print(ticks/drive_ticks);
}



publish("/cmd_vel", "geometry_msgs/msg/Twist", {
    "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
    "angular": {"x": 0.0, "y": 0.0, "z": 0.0}
});



print("stopping");

wait(2); #this final wait gives the ros bridge time to send the 0 vel message before exiting

print("stopped");
```

# Debugging

If you cannot get commands to send to the robot or cannot view the nodes or topics in rqt this is likely an issue with ufw again. Simply modify the ufw table on the robot to allow inbound udp traffic from anyting on the 192.168.1.0/24 subnet and it should be fine.


For some reason despite what the /cmv_vel topic recieves the cmd_vel to servo translation layer on the robot will always set these values to 0 or 0.73... for the trottle and 0 or 1 for the steering servo. I have no idea why this is but is something that needs to be addressed sooner than later.

# Future notes

At some point we should move these to be cli args to environment variables to be more consistant with the ros ecosystem
