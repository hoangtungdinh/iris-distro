from __future__ import division
import numpy as np
import gurobipy

def compute_obstacle_planes(obstacle_pts, C, d):
    dim = C.shape[0]
    infeas_start = False
    Cinv = np.linalg.inv(C);
    n_obs = obstacle_pts.shape[2]
    pts_per_obstacle = obstacle_pts.shape[1]

    uncovered_obstacles = np.ones(n_obs, dtype=np.bool)
    image_pts = Cinv.dot(obstacle_pts.reshape((dim,-1)) - d.reshape((-1,1))).reshape(obstacle_pts.shape)
    image_dists = np.sum(np.power(image_pts, 2), axis=0)
    obs_image_dists = np.min(image_dists, axis=0)
    obs_sort_idx = np.argsort(obs_image_dists)

    ais = []
    bs = []

    for i in obs_sort_idx:
        if not uncovered_obstacles[i]:
            continue

        obs = obstacle_pts[:,:,i]
        ys = image_pts[:,:,i]

        dists = image_dists[:,i]
        idx = np.argmin(dists)
        yi = ys[:,idx]
        xi = obs[:,idx]
        nhat = 2 * (Cinv.dot(Cinv.T)).dot(xi - d)
        nhat = nhat / np.linalg.norm(nhat)
        b0 = nhat.dot(xi)
        if np.all(nhat.dot(obs) - b0 >= 0):
            # nhat is feasible, so we can skip the optimization
            ai = nhat
            bi = b0
        else:
            m = gurobipy.Model("ldp")
            ws = [m.addVar(lb=0, ub=1) for j in range(pts_per_obstacle)]
            vs = [m.addVar(lb=-gurobipy.GRB.INFINITY, ub=gurobipy.GRB.INFINITY) for j in range(dim)]
            m.update()
            for j in range(dim):
                con = gurobipy.LinExpr()
                m.addConstr(gurobipy.LinExpr(list(ys[j,:]), ws) == vs[j])
            m.addConstr(gurobipy.quicksum(ws) == 1)
            m.setObjective(gurobipy.quicksum([vs[j] * vs[j] for j in range(dim)]))
            m.optimize()
            ystar = np.array([v.x for v in vs])
            if np.linalg.norm(ystar) < 1e-3:
                # d is inside the obstacle. So we'll just reverse nhat to try
                # to push the ellipsoid out of the obstacle.
                print "Warning: ellipse center is inside an obstacle"
                infeas_start = True
                ai = -nhat
                bi = -nhat.dot(xi)
            else:
                xstar = C.dot(ystar) + d
                nhat = 2 * Cinv.dot(Cinv.T).dot(xstar - d)
                nhat = nhat / np.linalg.norm(nhat)
                ai = nhat
                bi = nhat.dot(xstar)

        ais.append(ai)
        bs.append(bi)
        check = ai.dot(obstacle_pts.reshape((dim, -1))) - bi >= 0
        check = check.reshape(obstacle_pts.shape[1:])
        excluded_mask = np.all(check, axis=0)
        uncovered_obstacles[excluded_mask] = False
        uncovered_obstacles[i] = False

        if not np.any(uncovered_obstacles):
            break

    A = np.vstack(ais)
    b = np.hstack(bs)
    return A, b, infeas_start