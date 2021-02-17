#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
 Created on 17-02-2021 15:48:25

 [Description]
"""
__author__ ="Benedict Wilkins"
__email__ = "benrjw@gmail.com"
__status__ ="Development"


# TAKEN FROM STABLE BASELINES

from collections import deque

from ..image import image
from ..np_wrap import Stack

import numpy as np
import gym
from gym import spaces

class NoopResetEnv(gym.Wrapper):

    def __init__(self, env, noop_max=30):
        """
            Sample initial states by taking random number of no-ops on reset.
            No-op is assumed to be action 0.

            :param env: (Gym Environment) the environment to wrap
            :param noop_max: (int) the maximum value of no-ops to run
        """
        gym.Wrapper.__init__(self, env)
        self.noop_max = noop_max
        self.override_num_noops = None
        self.noop_action = 0
        assert env.unwrapped.get_action_meanings()[0] == 'NOOP'

    def reset(self, **kwargs):
        self.env.reset(**kwargs)
        if self.override_num_noops is not None:
            noops = self.override_num_noops
        else:
            noops = self.unwrapped.np_random.randint(1, self.noop_max + 1)
        assert noops > 0
        obs = None
        for _ in range(noops):
            obs, _, done, _ = self.env.step(self.noop_action)
            if done:
                obs = self.env.reset(**kwargs)
        return obs

    def step(self, action):
        return self.env.step(action)

class FireResetEnv(gym.Wrapper):

    def __init__(self, env):
        """
            Take action on reset for environments that are fixed until firing.

            :param env: (Gym Environment) the environment to wrap
        """
        gym.Wrapper.__init__(self, env)
        assert env.unwrapped.get_action_meanings()[1] == 'FIRE'
        assert len(env.unwrapped.get_action_meanings()) >= 3

    def reset(self, **kwargs):
        self.env.reset(**kwargs)
        obs, _, done, _ = self.env.step(1)
        if done:
            self.env.reset(**kwargs)
        obs, _, done, _ = self.env.step(2)
        if done:
            self.env.reset(**kwargs)
        return obs

    def step(self, action):
        return self.env.step(action)

class EpisodicLifeEnv(gym.Wrapper):

    def __init__(self, env):
        """
            Make end-of-life == end-of-episode, but only reset on true game over.
            Done by DeepMind for the DQN and co. since it helps value estimation.

            :param env: (Gym Environment) the environment to wrap
        """
        gym.Wrapper.__init__(self, env)
        self.lives = 0
        self.was_real_done = True

    def step(self, action):
        obs, reward, done, info = self.env.step(action)
        self.was_real_done = done
        # check current lives, make loss of life terminal,
        # then update lives to handle bonus lives
        lives = self.env.unwrapped.ale.lives()
        if 0 < lives < self.lives:
            # for Qbert sometimes we stay in lives == 0 condtion for a few frames
            # so its important to keep lives > 0, so that we only reset once
            # the environment advertises done.
            done = True
        self.lives = lives
        return obs, reward, done, info

    def reset(self, **kwargs):
        """
        Calls the Gym environment reset, only when lives are exhausted.
        This way all states are still reachable even though lives are episodic,
        and the learner need not know about any of this behind-the-scenes.

        :param kwargs: Extra keywords passed to env.reset() call
        :return: ([int] or [float]) the first observation of the environment
        """
        if self.was_real_done:
            obs = self.env.reset(**kwargs)
        else:
            # no-op step to advance from terminal/lost life state
            obs, _, _, _ = self.env.step(0)
        self.lives = self.env.unwrapped.ale.lives()
        return obs


class MaxAndSkipEnv(gym.Wrapper):

    def __init__(self, env, skip=4):

        """
            Return only every `skip`-th frame (frameskipping)

            :param env: (Gym Environment) the environment
            :param skip: (int) number of `skip`-th frame
        """
        gym.Wrapper.__init__(self, env)
        # most recent raw observations (for max pooling across time steps)
        self._obs_buffer = np.zeros((2,) + env.observation_space.shape, dtype=env.observation_space.dtype)
        self._skip = skip

    def step(self, action):
        """
        Step the environment with the given action
        Repeat action, sum reward, and max over last observations.

        :param action: ([int] or [float]) the action
        :return: ([int] or [float], [float], [bool], dict) observation, reward, done, information
        """
        total_reward = 0.0
        done = None
        for i in range(self._skip):
            obs, reward, done, info = self.env.step(action)
            if i == self._skip - 2:
                self._obs_buffer[0] = obs
            if i == self._skip - 1:
                self._obs_buffer[1] = obs
            total_reward += reward
            if done:
                break
        # Note that the observation on the done=True frame
        # doesn't matter
        max_frame = self._obs_buffer.max(axis=0)

        return max_frame, total_reward, done, info

    def reset(self, **kwargs):
        return self.env.reset(**kwargs)


class ClipRewardEnv(gym.RewardWrapper):
    def __init__(self, env):
        """
        clips the reward to {+1, 0, -1} by its sign.

        :param env: (Gym Environment) the environment
        """
        gym.RewardWrapper.__init__(self, env)

    def reward(self, reward):
        """
        Bin reward to {+1, 0, -1} by its sign.

        :param reward: (float)
        """
        return np.sign(reward)

def wrap_atari(env, episode_life=False, clip_rewards=True, frame_stack=4):
    """
        Create a wrapped atari Environment

        :param env_id: (str) the environment ID
        :param episode_life: (bool) wrap the episode life wrapper
        :param clip_rewards: (bool) wrap the reward clipping wrapper
        :param frame_stack: (bool) wrap the frame stacking wrapper
        :return: (Gym Environment) the wrapped atari environment
    """

    assert 'NoFrameskip' in env.spec.id

    env = NoopResetEnv(env, noop_max=30)

    env = MaxAndSkipEnv(env, skip=4)

    if episode_life:
        env = EpisodicLifeEnv(env)

    if 'FIRE' in env.unwrapped.get_action_meanings():
        env = FireResetEnv(env)

    env = image(env).grey((1/3,1/3,1/3))
    env = env.resize(84,84,1).CHW() / 255

    if clip_rewards:
        env = ClipRewardEnv(env)
    
    if frame_stack > 1:
        env = Stack(env, n=frame_stack, dim=0)
    return env

   
