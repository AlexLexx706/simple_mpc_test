import math
import logging
from typing import Tuple, List, Union
import numpy as np
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets
from mpc import mpc_back_box
from mpc import mpc_casadi

LOG = logging.getLogger(__name__)


class CarModel(QtWidgets.QGraphicsItemGroup):
    """Visualization of car with trailer
    """
    PERIOD = 10.  # Time period for steering change
    MAX_ANGLE = math.radians(25.)  # Maximum steering angle in radians
    MAX_RATE = math.radians(30)  # Maximum steering angle in radians
    MAX_TRAILER_ANGLE = math.radians(30)  # Maximum steering angle in radians
    WIDTH = 3  # default width base, m
    WHEEL_BASE = 5  # default wheel base, m
    TRAILER_WIDTH = 2.  # default Length of the trailer, m
    WHEEL_LEN = 1.  # default Length of the wheels, m
    WHEEL_WIDTH = 0.3  # default Width of the wheels, m
    STEERING_ANGLE = 0.  # Initial steering angle (in radians)
    TRAILER_LEN = 5  # Length of the trailer, m
    TRAILER_OFFSET = 0.  # offset of trailer joint, m
    TRAILER_CTRL_POINT = [0., 3.]  # Steering point in trailer frame, m
    RADIUS = 5.  # bounding circle radius, m
    SPEED = 5   # Car speed m/s

    XTRACK_WEIGHT = 1.
    HEADING_WEIGHT = 30
    DT = 0.1

    LINE_PEN = QtGui.QPen(QtGui.QColor(0, 0, 0), 2)
    LINE_PEN.setCosmetic(True)

    BODY_COLOR = QtGui.QColor(0, 0, 255)  # Blue color for the car body
    WHEEL_COLOR = QtGui.QColor(255, 0, 0)

    CONTROL_POINT_PEN = QtGui.QPen(QtGui.QColor(0, 0, 255), 10)
    CONTROL_POINT_PEN.setCosmetic(True)
    CONTROL_POINT_PEN.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)

    CIRCLE_BRUSH = QtGui.QBrush(QtCore.Qt.black, QtCore.Qt.NoBrush)

    CTRL_POINT_RADIUS = 0.3
    CTRL_POINT_PEN = QtGui.QPen(QtCore.Qt.black, 2)
    CTRL_POINT_PEN.setCosmetic(True)
    CTRL_POINT_BRUSH = QtCore.Qt.black

    def __init__(
            self,
            circles_num: int,
            path_len: int,
            dt: float,
            steps: int,
            max_iter: int,
            soft_constrain: bool):
        """Create new car with mpc

        Args:
            circles_num (int): number of circle constrain
            path_len (int): number of path points
            dt (float): dt
            steps (int): number of prediction horizon
            max_iter (int): sorver settings
            soft_constrain (bool): type of constrain
        """
        super().__init__()
        self.speed = self.SPEED
        self.setFlags(
            self.ItemIsMovable
            | self.ItemIsSelectable
            | self.ItemSendsGeometryChanges)

        # set geometry of the car:
        self.body = QtWidgets.QGraphicsRectItem(
            0,
            -self.WIDTH / 2.,
            self.WHEEL_BASE,
            self.WIDTH,
            self)
        self.body.setPen(self.LINE_PEN)
        self.body.setBrush(self.BODY_COLOR)

        self.front_left_wheel = QtWidgets.QGraphicsRectItem(
            -self.WHEEL_LEN / 2.,
            -self.WHEEL_WIDTH / 2.,
            self.WHEEL_LEN,
            self.WHEEL_WIDTH,
            self)
        self.front_left_wheel.setPos(self.WHEEL_BASE, -self.WIDTH / 2.)
        self.front_left_wheel.setPen(self.LINE_PEN)
        self.front_left_wheel.setBrush(self.WHEEL_COLOR)

        self.front_right_wheel = QtWidgets.QGraphicsRectItem(
            self.front_left_wheel.rect(),
            self)
        self.front_right_wheel.setPos(self.WHEEL_BASE, self.WIDTH / 2.)
        self.front_right_wheel.setPen(self.LINE_PEN)
        self.front_right_wheel.setBrush(self.WHEEL_COLOR)

        self.rear_left_wheel = QtWidgets.QGraphicsRectItem(
            self.front_left_wheel.rect(),
            self)
        self.rear_left_wheel.setPos(0., -self.WIDTH / 2.)
        self.rear_left_wheel.setPen(self.LINE_PEN)
        self.rear_left_wheel.setBrush(self.WHEEL_COLOR)

        self.rear_right_wheel = QtWidgets.QGraphicsRectItem(
            self.front_left_wheel.rect(),
            self)
        self.rear_right_wheel.setPos(0., self.WIDTH / 2.)
        self.rear_right_wheel.setPen(self.LINE_PEN)
        self.rear_right_wheel.setBrush(self.WHEEL_COLOR)

        self.trailer = QtWidgets.QGraphicsRectItem(
            -self.TRAILER_LEN,
            -self.TRAILER_WIDTH / 2.,
            self.TRAILER_LEN,
            self.TRAILER_WIDTH,
            self)
        self.trailer.setPen(self.LINE_PEN)
        self.trailer.setBrush(self.BODY_COLOR)

        self.trailer_left_wheel = QtWidgets.QGraphicsRectItem(
            self.front_left_wheel.rect(),
            self.trailer)
        self.trailer_left_wheel.setPos(
            -self.TRAILER_LEN,
            -self.TRAILER_WIDTH / 2.)
        self.trailer_left_wheel.setPen(self.LINE_PEN)
        self.trailer_left_wheel.setBrush(self.WHEEL_COLOR)

        self.trailer_right_wheel = QtWidgets.QGraphicsRectItem(
            self.front_left_wheel.rect(),
            self.trailer)
        self.trailer_right_wheel.setPos(
            -self.TRAILER_LEN,
            self.TRAILER_WIDTH / 2.)
        self.trailer_right_wheel.setPen(self.LINE_PEN)
        self.trailer_right_wheel.setBrush(self.WHEEL_COLOR)

        self.circle = QtWidgets.QGraphicsEllipseItem(
            -self.RADIUS,
            -self.RADIUS,
            2 * self.RADIUS,
            2 * self.RADIUS,
            self)
        self.circle.setPen(self.LINE_PEN)

        self.ctrl_point = QtWidgets.QGraphicsEllipseItem(
            -self.CTRL_POINT_RADIUS,
            -self.CTRL_POINT_RADIUS,
            2 * self.CTRL_POINT_RADIUS,
            2 * self.CTRL_POINT_RADIUS,
            self.trailer)
        self.ctrl_point.setPos(
            self.TRAILER_CTRL_POINT[0] - self.TRAILER_LEN,
            self.TRAILER_CTRL_POINT[1])
        self.ctrl_point.setPen(self.CTRL_POINT_PEN)
        self.ctrl_point.setBrush(self.CTRL_POINT_BRUSH)

        # MPC controller
        self.mpc = mpc_casadi.MPCCasadi(
            steps=steps,
            max_iter=max_iter,
            soft_constrain=soft_constrain,
            circles_num=circles_num,
            path_len=path_len)

    def set_wheel_base(self, wheel_base: float):
        """setup wheel_base

        Args:
            wheel_base (float): wheel base, m
        """
        rect = self.body.rect()
        rect.setWidth(wheel_base)
        self.body.setRect(rect)
        self.front_left_wheel.setPos(wheel_base, -self.WIDTH/2)
        self.front_right_wheel.setPos(wheel_base, self.WIDTH/2)

    def get_wheel_base(self) -> float:
        """return wheel base

        Returns:
            _type_: wheel base
        """
        return self.body.rect().width()

    def set_trailer_len(self, trailer_len: float):
        """set trailer len

        Args:
            trailer_len (float): trailer len
        """
        self.trailer.setRect(
            -trailer_len,
            -self.TRAILER_WIDTH / 2.,
            trailer_len,
            self.TRAILER_WIDTH)

        self.trailer_left_wheel.setPos(
            -trailer_len,
            -self.TRAILER_WIDTH / 2.)

        self.trailer_right_wheel.setPos(
            -trailer_len,
            self.TRAILER_WIDTH / 2.)

    def get_trailer_len(self) -> float:
        """return trailer len

        Returns:
            float: trailer len
        """
        return self.trailer.rect().width()

    def rebuild_mpc(
            self,
            circles_num: int,
            path_len: int,
            dt: float,
            steps: int,
            max_iter: int,
            soft_constrain: bool):
        """Create new car with mpc

        Args:
            circles_num (int): number of circle constrain
            path_len (int): number of path points
            dt (float): dt
            steps (int): number of prediction horizon
            max_iter (int): sorver settings
            soft_constrain (bool): type of constrain
        """
        self.mpc = mpc_casadi.MPCCasadi(
            steps=steps,
            max_iter=max_iter,
            soft_constrain=soft_constrain,
            circles_num=circles_num,
            path_len=path_len)

    def predict(
            self,
            path: List[Tuple[float, float]],
            circles_obstacle: List[Tuple[float, float, float]]) -> Tuple[
                List[Tuple[float, float, float, float]],
                List[Tuple[float, float, float, float]]]:
        """Moves the car based on MPC, by updating its position and orientation

        Args:
            path List[Tuple[float, float]]: path
            circles_obstacle List[Tuple[float, float, float]] : descriptions of circle obstacles: [[x,y,radius],...]
        Returns:
            Tuple[
                List[Tuple[float, float, float, float]],
                List[Tuple[float, float, float, float]]]: tuple of [states, control_angles]:
                    states : List[Tuple[x, y, heading, trailer_heading],...] - len depends from MPC model
                    control_angles: List[angle,...] - len depends from MPC model
        """
        heading = self.rotation()
        state = np.array([
            self.x(),
            self.y(),
            math.radians(heading),
            math.radians(heading + self.trailer.rotation())])

        ctrl_point_pos = self.ctrl_point.pos()
        trailer_len = self.trailer.rect().width()
        return self.mpc.optimize_controls(
            self.DT,
            path,
            state,
            math.radians(self.front_left_wheel.rotation()),
            self.speed,
            self.body.rect().width(),
            self.MAX_RATE,
            self.MAX_ANGLE,
            self.MAX_TRAILER_ANGLE,
            trailer_len,
            self.TRAILER_OFFSET,
            (trailer_len - ctrl_point_pos.x(), ctrl_point_pos.y()),
            self.XTRACK_WEIGHT,
            self.HEADING_WEIGHT,
            circles_obstacle,
            self.circle.rect().width() / 2.)

    def move(
            self,
            dt: float,
            line: Tuple[Tuple[float, float], Tuple[float, float]],
            circles_obstacle: List[Tuple[float, float, float]]) -> Union[
                None, Tuple[
                    List[Tuple[float, float, float, float]],
                    List[Tuple[float, float, float, float]]]]:
        """Moves the car based on MPC, by updating its position and orientation

        Args:
            dt (float): dt, sec
            line (Tuple[Tuple[float, float], Tuple[float, float]]): line path description:
                A point: [x,y]
                B point: [x,y]
            circles_obstacle List[Tuple[float, float, float]] : descriptions of circle obstacles: [[x,y,radius],...]
        Returns:
            Union[None, Tuple[
                List[Tuple[float, float, float, float]],
                List[Tuple[float, float, float, float]]]]: None - no solution or tuple of [states, control_angles]:
                states : List[Tuple[x, y, heading, trailer_heading],...] - len depends from MPC model
                control_angles: List[angle,...] - len depends from MPC model
        """
        try:
            solution = self.predict(line, circles_obstacle)
            heading = self.rotation()
            state = np.array([
                self.x(),
                self.y(),
                math.radians(heading),
                math.radians(heading + self.trailer.rotation())])
        except ValueError as e:
            # optimization fails
            LOG.error(e)
            return

        # Update car state
        steering_angle = float(solution[1][1])
        state += mpc_back_box.MPCBlackBox.trailer_model(
            state,
            self.speed,
            steering_angle,
            self.body.rect().width(),
            self.trailer.rect().width(),
            0)[:4] * dt

        self.front_left_wheel.setRotation(math.degrees(steering_angle))
        self.front_right_wheel.setRotation(math.degrees(steering_angle))
        self.setPos(state[0], state[1])
        self.setRotation(math.degrees(state[2]))
        self.trailer.setRotation(math.degrees(state[3] - state[2]))
        return solution
