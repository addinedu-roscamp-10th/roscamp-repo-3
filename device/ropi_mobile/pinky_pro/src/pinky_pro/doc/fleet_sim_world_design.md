# Fleet Simulation World Design

## Goal

Design a larger Gazebo practice world for:

- `2 x Pinky Pro` first
- later `3 x Pinky Pro + 2 x Jetcobot arms`
- ROS 2 multi-robot simulation
- fleet task dispatch, waiting, rerouting, and station handling

The world should force real traffic interactions instead of letting each robot drive in open space without conflict.

## Scenario

Use a small intralogistics cell rather than a generic empty warehouse.

The robots move between:

- inbound loading
- storage aisles
- 2 arm workcells
- outbound handoff
- charger / parking area

This gives enough structure to practice:

- multi-robot namespacing
- per-robot Nav2
- task dispatch
- station reservation
- queueing at bottlenecks
- collision avoidance at shared corridors

## World Size

Recommended first version:

- overall floor: `18.0 m x 12.0 m`
- wall height: `2.2 m`
- usable driving area inside walls: about `17.2 m x 11.2 m`

This is large enough for:

- long routes
- at least 2 intersections
- 2 narrow shared corridors
- separate work areas

## Top-Down Layout

Coordinate convention:

- origin near world center
- `+x` to the east
- `+y` to the north

Suggested zone placement:

```text
 y+
  6.0  +-------------------------------------------------------------+
       | P1  P2  P3  | CHARGERS |            NORTH CORRIDOR          |
       | staging     |   C1 C2  |------------------------------------|
       |-------------+----------+                                    |
       |                                                            A1|
       |   STORAGE Aisle A      MAIN CROSS AISLE      STORAGE B      ||
       |   S1   S2   S3                               S4   S5   S6   ||
       |                                                             ||
       |--------------------------+--------------------------+--------||
       | inbound / loading L1 L2  | central queue / merge    | arm 1 ||
       |                           | point Q1                | cell   ||
       |--------------------------+--------------------------+--------||
       | outbound / pack O1 O2    | south corridor           | arm 2 ||
 -6.0  | robot spawn R1 R2        |                          | cell   ||
       +-------------------------------------------------------------+ -> x+
        -9.0                                                      +9.0
```

## Functional Zones

### 1. Parking and charger zone

Purpose:

- default idle positions
- startup spawn area
- battery / dock simulation later

Suggested placement:

- north-west corner
- `x = -8.0 to -4.5`
- `y = 3.8 to 5.5`

Required elements:

- 3 parking pads: `P1`, `P2`, `P3`
- 2 charger pads: `C1`, `C2`

Notes:

- `P3` is reserved for future `pinky_3`
- keep at least `0.7 m` center-to-center spacing between pads

### 2. Inbound loading zone

Purpose:

- pickup tasks
- queueing behavior

Suggested placement:

- west-central / south-west
- `x = -8.2 to -4.8`
- `y = -1.8 to 0.5`

Required elements:

- 2 pallet or tote stations: `L1`, `L2`
- 1 waiting pocket before merge

Notes:

- make this area wide enough for one robot to wait while another departs

### 3. Outbound / packing zone

Purpose:

- dropoff tasks
- repeated fleet missions

Suggested placement:

- south-west
- `x = -8.2 to -4.8`
- `y = -5.2 to -2.7`

Required elements:

- 2 stations: `O1`, `O2`
- 1 queue waypoint for dispatch tests

### 4. Storage aisles

Purpose:

- create navigation distance
- create narrow corridors and aisle entry conflicts

Suggested placement:

- central band across the map
- `x = -4.0 to 4.5`
- `y = -0.8 to 3.8`

Structure:

- 6 shelf groups: `S1` to `S6`
- 2 long aisles with width `0.9 m to 1.1 m`
- 1 cross aisle with width `1.6 m`

Notes:

- aisle width should be intentionally tight but still navigable
- this is the main area where two Pinky robots must negotiate shared space

### 5. Central merge / queue zone

Purpose:

- force routing conflicts
- give the fleet manager a natural reservation point

Suggested placement:

- near center-south
- around `x = 0.0`, `y = -1.2`

Required elements:

- named waypoint `Q1`
- at least 3 incoming edges in the traffic graph

Notes:

- all tasks from loading to arms or storage should tend to cross this point

### 6. Arm workcell 1

Purpose:

- future Jetcobot integration
- pickup/dropoff interface station

Suggested placement:

- east-middle
- `x = 5.5 to 8.2`
- `y = -0.5 to 2.5`

Required elements:

- one static workbench
- one arm pedestal
- one robot stop pose: `A1_APPROACH`
- one handoff pose: `A1_DOCK`

Notes:

- for phase 1, the arm can remain static scenery
- reserve clearance so the mobile base does not block the north corridor

### 7. Arm workcell 2

Purpose:

- second task destination
- future dual-arm sequencing

Suggested placement:

- east-south
- `x = 5.5 to 8.2`
- `y = -4.8 to -2.0`

Required elements:

- one static workbench
- one arm pedestal
- one robot stop pose: `A2_APPROACH`
- one handoff pose: `A2_DOCK`

## Driving Geometry

Use these widths as design rules:

- main corridor: `1.8 m`
- standard corridor: `1.2 m to 1.4 m`
- narrow aisle: `0.9 m to 1.1 m`
- docking pocket depth: `0.8 m`
- turn pocket at intersections: at least `1.4 m x 1.4 m`

These values should be checked against the actual Pinky footprint and Nav2 inflation settings.

## Robot Initial Poses

Phase 1:

- `pinky_1`: parking pad `P1`, near `(-7.4, 4.8, 0.0)`
- `pinky_2`: parking pad `P2`, near `(-6.1, 4.8, 0.0)`

Future:

- `pinky_3`: parking pad `P3`, near `(-4.8, 4.8, 0.0)`

Yaw suggestions:

- all facing east on startup

## Traffic Editor / Lane Graph Design

The traffic graph should be designed separately from the occupancy map.

### Required waypoint categories

- `parking`: `P1`, `P2`, `P3`
- `charger`: `C1`, `C2`
- `load`: `L1`, `L2`
- `output`: `O1`, `O2`
- `storage access`: `S1_ENTRY` to `S6_ENTRY`
- `queue`: `Q1`, `Q2`
- `arm approach`: `A1_APPROACH`, `A2_APPROACH`
- `arm dock`: `A1_DOCK`, `A2_DOCK`

### Required traffic behaviors

- at least 1 one-way segment inside a narrow aisle
- at least 2 bidirectional corridors
- at least 1 queue before each arm dock
- at least 1 bypass route around the storage area

### Recommended graph pattern

- ring corridor around the storage area
- central east-west cross aisle
- north corridor connecting parking to east workcells
- south corridor connecting output area to east workcells

This gives multiple route choices and makes dispatch policy meaningful.

## Assets To Build Or Reuse

Reuse from the current repository:

- shelf model from `pinky_gz_sim/models/shelf`
- Pinky robot model from `pinky_description`
- current wall and floor primitives as a starting point

Add new simple assets first:

- charger pad
- pallet / tote station
- conveyor or packing table blocks
- workbench for each arm cell
- safety fence blocks around arm cells
- floor markings for lanes and stations

Do not start with detailed meshes.
Primitive-based assets are better until navigation, traffic, and spawning are stable.

## World Files To Produce

Recommended artifacts:

- `pinky_fleet_sim/worlds/fleet_practice_large.world`
- `pinky_fleet_sim/maps/fleet_practice_large.yaml`
- `pinky_fleet_sim/maps/fleet_practice_large.pgm`
- `pinky_fleet_sim/traffic/fleet_practice_large.building.yaml`
- `pinky_fleet_sim/config/robots.yaml`

## Map Production Flow

Recommended order:

1. Build the Gazebo world with named zones and simple geometry.
2. Spawn one robot and verify manual driving through all corridors.
3. Run SLAM or export a controlled occupancy map.
4. Clean the map for Nav2.
5. Build the traffic graph on top of the cleaned floor plan.
6. Add the second robot and test conflicting routes.

## Practice Scenarios

The world should support these training tasks:

### Scenario A: Two independent deliveries

- `pinky_1`: `L1 -> S2_ENTRY -> O1`
- `pinky_2`: `L2 -> A1_DOCK -> O2`

Expected behavior:

- both robots cross at least one shared merge

### Scenario B: Shared workcell queue

- both robots are sent to `A1_DOCK`

Expected behavior:

- one robot waits at `A1_APPROACH` or queue waypoint

### Scenario C: Corridor contention

- one robot drives east through the storage cross aisle
- the other drives west through the same corridor

Expected behavior:

- test dispatch-level waiting or local avoidance policy

### Scenario D: Charger return

- after task completion, both robots return to parking or chargers

Expected behavior:

- non-task goals exist and do not deadlock the map

## Phase Plan

### Phase 1: Large map for 2 Pinky robots

- build the large world
- add simple assets only
- spawn `pinky_1` and `pinky_2`
- enable manual teleop and namespaced topics

### Phase 2: Multi-robot Nav2

- generate the occupancy map
- run namespaced Nav2 for each robot
- verify both robots can localize and navigate

### Phase 3: Fleet practice layer

- add task stations and a simple dispatcher
- support queueing and station reservation

### Phase 4: Final expansion

- add `pinky_3`
- replace static arm placeholders with `2 x Jetcobot` cells

## Acceptance Criteria

The design is good enough when:

- two robots can start without overlap
- both robots can traverse the entire map
- at least 2 natural choke points exist
- at least 6 distinct station goals exist
- there is enough room for a future third robot without redesigning the world
- the arm cells are already reserved in the layout even if their controllers are not implemented yet

## Recommended Next Implementation Step

Implement the world shell first:

- floor
- outer walls
- shelf blocks
- charger zone
- loading zone
- output zone
- two arm cell placeholders

Do not implement detailed traffic logic before the physical layout and spawn geometry are proven in Gazebo.
