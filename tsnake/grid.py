"""
Module containing implementations of the ACID technique.
"""

import numpy as np
import snake as snake
import cv2


class Point(object):
    """
    Represents a point on a grid with x and y components
    """

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.adjacent_edges = dict()
        # self.adjacent_points = set()

    # TODO@allen:
    # each point keeps track of edges and maintains set of all points
    # associated with the edges that start or terminate on that point
    # when adding a new edge between points, ensure that the pair of points doesn't
    # already have that edge, if it does, assign the one that already exists

    def add_edge(self, edge):
        '''
        Add given edge to the dict of edges connected to this node
        args:
        * edge: GridCellEdge connected to this node
        return:
        * None: Stores edge in self.adjacent_edges dictionary
        '''
        self.adjacent_edges[edge] = edge

    @property
    def position(self):
        return np.array([self.x, self.y]).reshape(1, 2)

    def __str__(self):
        return "({}, {})".format(self.x, self.y)

    def __repr__(self):
        return self.__str__()  # + ":" + str(self.__hash__()) #NOTE: For debugging, can add hash

    def __hash__(self):
        return hash((self.x, self.y))

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def __lt__(self, other):
        if self.x != other.x:
            return self.x < other.x
        else:
            return self.y < other.y


class GridCellEdge(object):
    """
    Represents one of the sides / cell-edges in the grid. 
    """

    def __init__(self, point1: Point, point2: Point) -> None:
        """
        Represents one grid cell edge (one of three components of a TriangeCell).

        Args:
        ==========================================
        * point1: Point(), for first (origin) point of the line segment
        * point2: Point(), the terminal point of the line segment
        ==========================================
        Return:
        ==========================================
        * None
        ==========================================
        """
        pts = sorted([point1, point2])
        self._point1 = pts[0]  # todo maybe argchecks
        self._point2 = pts[1]

        # TODO: implement this data structure
        self.intersections = list()

    @property
    def endpoints(self):
        return np.array([self._point1, self._point2])  # .reshape(1, 2)

    def __str__(self):
        return "<{}, {}>".format(str(self._point1), str(self._point2))

    def __repr__(self):
        return self.__str__() + ":" + str(self.__hash__())

    def __hash__(self):
        return hash((self._point1, self._point2))

    def __eq__(self, other):
        return self._point1 == other._point1 and self._point2 == other._point2

    def add_intersection(self, point: Point) -> None:
        """
        Store the intersection in the edge
        Arguments:
        -------------------------------
        * point: Point(), point object representing where the intersection occured
        -------------------------------
        Return:
        -------------------------------
        * None
        -------------------------------
        """
        self.intersections.append(point)

    def find_intersection_point_with_element(self, element):
        """
        If this grid cell edge intersects with the given element:
            - Return the point of intersection (2-tuple of the coordinates).
        Else:
            - Return None
        """
        raise NotImplementedError


class Grid(object):
    """
    Class representing the entire cell grid (of triangles) for an image.
      - image meaning the blank space the T-snake is segmenting / infilling
      - assumes that each triangle-cell is a right triangle
        (for the Coxeter-Freudenthal triangulation) (see Fig 2 in the paper)

      - assumes (for now) that the space we're segmenting / infilling is rectangular


    In the paper, Demetri mentions the 'Freudenthal triangulation' for 
    implementing the cell-grid:
     https://www.cs.bgu.ac.il/~projects/projects/carmelie/html/triang/fred_T.htm

    Args:
    ==========================================
    (np.array) image:
    * (n by m) matrix representing the color image.

    (float) scale:
    * float between 0 and 1 representing the number of pixels per cell, i.e. 1=1 vertex/pixel, .5 = 2 vertex per pixel, so on

    ==========================================
    """

    def __init__(self, image, scale=1.0):
        """
        @allen: Should we pass a snake to the board? should the board own the snake?
        TODO: implement Freudenthal triangulation
        https://www.cs.bgu.ac.il/~projects/projects/carmelie/html/triang/fred_T.htm
        """
        assert isinstance(image, np.ndarray)
        assert len(image.shape) == 3  # height * width * color channels

        # Raw image
        self.image = image
        self.m, self.n, self.d = image.shape

        # Image matrix after force and intensity function
        self.image_force = None
        self.image_intensity = None

        # Simplex Grid Vars

        if scale >= 1:
            s = "Scale > 1 must be an integer multiple of image size."
            assert self.m % scale == 0, s
            assert self.n % scale == 0, s
        elif scale > 0:
            inv = 1/float(scale)
            assert inv.is_integer(), "If scale < 1, 1/scale must be an integer"
        else:
            assert False, "Scale must be > 0."
        self.scale = scale
        self.grid = None

        # Hash map containing [Point(upper left corner)]:all edges in pair of simplicies
        self.point_edge_map = dict()
        self.edges = dict()  # set of all edges
        self._snakes = list()  # All the snakes on this grid
        # print("Grid initialized with:\n\theight: {}\n\twidth: {}\n\tdepth: {}".format(self.m, self.n, self.d))

    def _store_edge(self, p1: Point, p2: Point) -> None:
        """
        Store the edge between Points p1 and p2 in both p1 and p2,
        unless the edge already exists, then that edge is used
        args:
        * Point: p1, p2: two points to store edge between
        return:
        * None
        """
        edge = GridCellEdge(p1, p2)
        if edge in self.edges:
            edge = self.edges[edge]
        else:
            self.edges[edge] = edge
        p1.add_edge(edge)
        p2.add_edge(edge)

    def gen_simplex_grid(self):
        """
        Private method to generate simplex grid and edge map over image at given scale
        self.grid = np array of size (n/scale) * m/scale

        * Verticies are on if positive, off if negative, and contain 
            bilinearly interpolated greyscale values according to surrouding pixels

        * vertex position indicated by its x and y indicies
        """
        m_steps = None
        n_steps = None
        if self.scale <= 1:
            m_steps = int(self.m / self.scale)
            n_steps = int(self.n / self.scale)
        else:
            m_steps = int(self.scale / self.m)
            n_steps = int(self.scale / self.n)

        self.grid = np.empty((m_steps, n_steps), dtype=object)
        for i in range(m_steps):
            for j in range(n_steps):
                curr_pt = Point(i*self.scale, j*self.scale)
                self.grid[i, j] = curr_pt
                if j > 0:
                    p1 = self.grid[i, j-1]
                    self._store_edge(curr_pt, p1)  # horizontal edge

                if i > 0:
                    p1 = self.grid[i-1, j]
                    self._store_edge(curr_pt, p1)  # vertical edge
                    if j < n_steps - 1:
                        p2 = self.grid[i-1, j+1]
                        self._store_edge(curr_pt, p2)  # diagnoal edge

    def get_image_force(self, threshold):
        """
        Compute's force of self.image
        TODO: Use cole's image force computation, this one is incorrect
        Args:
        ========================
        (int) threshold:
        * integer threshold, pixels with intensities above this value will be set to 1, else 0
        ========================
        Return:
        ========================
        (np.array) force: 
        * (self.image.shape[0] by self.image.shape[1]) boolean array of 0 and 1
        ========================
        """
        if self.image_force is None:
            intensity = self.get_image_intensity()
            self.image_force = np.zeros(intensity.shape) - 1
            self.image_force[intensity >= threshold] = 1

        return self.image_force

    def get_image_intensity(self):
        """
        Compute's intensity of self.image

        Args:
        ========================
        None
        ========================
        Return:
        ========================
        (np.array) intensities: 
        * (self.image.shape[0] by self.image.shape[1]) array of of intensities (values of 0 to 255)
        ========================
        """
        if self.image_intensity is None:
            self.image_intensity = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
        return self.image_intensity

    def add_snake(self, new_snake):
        """
        Add a new snake to the grid
        """
        # assert isinstance(new_snake, snake.TSnake) # TODO: this line doesn't work
        self._snakes.append(new_snake)

    def get_closest_node(self, position: np.array) -> np.array:
        """
        Get the closest grid point to the coordinates 
        of the snake node passed in position
        args:
        * np array (1,2) containing x and y position of node
        return:
        * np array (1,2) containing self.grid index of closest grid point
        """
        # Integer divide to closest node
        pos_frac = position - np.fix(position)
        pos_whole = position - pos_frac
        remainder = np.fmod(pos_frac, self.scale)
        idx = np.array((position-remainder)/self.scale, dtype=int)
        return idx

    def get_cell_edges(self, index):
        """
        get all edges bounded by the box with the index
        position as it's top-left corner
        args:
        * index: np array (1,2) of index of bounding box's top-left corner
        returns:
        * edges: set() of all edges bounded by this box, i.e., potential intersection points
        """
        edges = set()
        for dx in [0, 1]:
            for dy in [0, 1]:
                pt = self.grid[index[0, 0]+dx, index[0, 1]+dy]
                for key in pt.adjacent_edges:
                    edges.add(pt.adjacent_edges[key])
        return edges

    @classmethod
    def perp(cls, a: np.array) -> np.array:
        """
        return the perpendicular of a 
        args:
        * a: (1,2) np array indicating a vector
        return:
        * b: (1,2) np array indicating a vector
        """
        b = np.empty_like(a)
        b[0] = -a[1]
        b[1] = a[0]
        return b

    @classmethod
    def dist(cls, a: np.array, b: np.array) -> float:
        """
        Return the distance between a and b
        args:

        """
        return np.sqrt(np.sum(np.power(a-b, 2)))

    @classmethod
    def seg_intersect(cls, a1, a2, b1, b2, decimal=3):
        """ 
        Returns the point of intersection of the lines passing through a2,a1 and b2,b1.
        Args: all are expected as (1,2) numpy arrays
        * a1: [x, y] a point on the first line
        * a2: [x, y] another point on the first line
        * b1: [x, y] a point on the second line
        * b2: [x, y] another point on the second line
        * decimal: int (optional): Number of decimals to round to, default is 3
        return:
        * (1,2) np array denoting [x, y] coordinates of intersection
        """
        s = np.vstack([a1, a2, b1, b2])        # s for stacked
        h = np.hstack((s, np.ones((4, 1))))  # h for homogeneous
        l1 = np.cross(h[0], h[1])           # get first line
        l2 = np.cross(h[2], h[3])           # get second line
        x, y, z = np.cross(l1, l2)          # point of intersection
        result = None
        if z == 0:                          # lines are parallel
            result = np.array([float('inf'), float('inf')]).reshape(1, 2)
        else:
            result = np.array([x/z, y/z]).reshape(1, 2)
        return np.around(result, decimal)

    def _get_element_intersection(self, element: snake.Element, edge: GridCellEdge) -> Point:
        """
        Get intersection between snake element and grid-cell-edge
        \nargs:\n
        * element: snake element, edge: GridCellEdge
        \nreturn:\n
        * Point: intersection point, or None if no intersection
        """
        s1, s2 = element.nodes  # TODO: Add to snake, (1,2) np array of [dx, dy]
        e1, e2 = edge.endpoints

        # Find intersection candidate
        intersection = self.seg_intersect(
            s1.position, s2.position, e1.position, e2.position)

        # Check if the two lines are parallel
        if intersection[0, 0] == float('inf'):
            return None

        # Check if it's too far from the snake element endpoints to be valid
        ds1 = self.dist(intersection, s1.position)
        ds2 = self.dist(intersection, s2.position)
        d_snake = self.dist(s1.position, s2.position)
        if ds2 > d_snake or ds1 > d_snake:
            return None

        # Check if it's too far from the GridCellEdge endpoints to be valid
        de1 = self.dist(intersection, e1.position)
        de2 = self.dist(intersection, e2.position)
        d_edge = self.dist(e1.position, e2.position)
        if de1 > d_edge or de2 > d_edge:
            return None

        return Point(intersection[0, 0], intersection[0, 1])

    def _compute_intersection(self, snake: snake.TSnake) -> [Point]:
        """
        Compute intersections between the grid and the snake in question
        \nArguments:\n
        * snake: snake.TSnake to compute intersections with
        \nReturn:\n
        * [Point]: contains all found intersection points. These points are also added to the intersection points of the edge
        """
        # TODO: KNOWN BUG: If the grid intersects a node's exact position, that intersection
        # is added to two edges (because the point is technically on two edges). Whatever the desired
        # behavor is, should be a relatively easy fix since points at same location hash the same
        elements = snake.elements  # TODO: Add this function to snake after merge
        intersections = []
        for element in elements:
            # Get all edges surrounding each node, and check each for intersections
            node1, node2 = element.nodes  # TODO: Add this function to snake after merge
            index = self.get_closest_node(node1.position)
            edges_to_check = self.get_cell_edges(index)
            for edge in edges_to_check:
                intersect_pt = self._get_element_intersection(element, edge)
                if intersect_pt is not None:
                    intersections.append(intersect_pt)
                    edge.add_intersection(intersect_pt)
                    # NOTE: Code to debug intersection points, see known bug above
                    # if np.sum(intersect_pt.position - node1.position) == 0 or np.sum(intersect_pt.position - node2.position) == 0:
                    #     print("Following intersection goes through existing point:")
                    # print("Edge: {}, Node1({}, {}), Node2({}, {}), index: {}, intersect point: {}".format(
                    #     edge, node1.position[0, 0], node1.position[0,1], node2.position[0, 0], node2.position[0, 1],
                    #     index, intersect_pt
                    # ))

        return intersections

    def get_snake_intersections(self) -> [[Point]]:
        """
        Compute intersections between all snakes on the grid and the grid.
        \nArgs:\n
        * None
        \nReturn:\n
        * list(list(Point)) containing the intersection points for each snake
        """
        intersections = []
        for snake in self._snakes:
            intersections.append(self._compute_intersection(snake))
        return intersections


### TODOS ###
# 1. snake updates - Joe
# 2. gan mask -> snake -> gan mask - Cole
# 3. algo phase 1: grid intersections - Allen
# 4. algo phase 2: turning nodes on / off, remove inactive points - Eric


if __name__ == '__main__':
    # Import testing
    positions = [(0.9, 0.9), (1.1, 0.9), (1.1, 1.1), (0.9, 1.1)]
    nodes = [snake.Node(p[0], p[1]) for p in positions]

    # NOTE: Manual Testing for image functions
    # Replace plane.png with any image locally in the folder
    img = cv2.imread("plane.png")
    grid = Grid(img, 0.5)
    grey = grid.get_image_intensity()
    force = grid.get_image_force(250)

    snake = snake.TSnake(nodes, force, grey, 1, 1, 1, 1)

    cv2.imshow("image", img)
    cv2.imshow("grey_image", grey)
    cv2.imshow("force_image", force)
    key = cv2.waitKey(0)

    pts = [[Point(1, 1), Point(1, 1)],
           [Point(1, 3), Point(1, 4)]]

    pts = np.array(pts)
    print("Representation format is (pt):hash")
    print(str(pts))
    assert pts[0][0] == pts[0][1], "Point's should be equal"

    grid.gen_simplex_grid()
    print("Simplex Grid shape: {}".format(grid.grid.shape))

    count = 0
    for i in range(grid.grid.shape[0]):
        for j in range(grid.grid.shape[1]):
            count += len(grid.grid[i, j].adjacent_edges)
    print("{} total edges, {} unique edges, total/unique = {}, expect about 2".format(
        count, len(grid.edges), count/len(grid.edges)))

    # Testing intersection finding math
    position = np.array([0.9, 0.9])
    pos_frac = position - np.fix(position)
    pos_whole = position - pos_frac
    remainder = np.fmod(pos_frac, 1)
    idx = np.array((position-remainder)/1, dtype=int)

    print("IDXS: {}".format(idx))

    a, b = np.array([1, 1]), np.array([2, 4])
    print(grid.dist(a, b))

    # testing actual intersection finding
    grid.add_snake(snake)
    intersections = grid.get_snake_intersections()
    print("Intersections, 6 expected, found {}".format(len(intersections[0])))
    print(intersections)
