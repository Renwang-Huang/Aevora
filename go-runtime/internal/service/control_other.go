//go:build !linux

package service

import "context"

func control(context.Context, ...string) (string, error) { return "", ErrUnavailable }
