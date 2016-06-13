import subprocess
import yaml
import re


def load_cfg(yaml_file):
    config = {}
    with open('config/default.yaml', 'r') as f:
        yaml_cfg = yaml.load(f.read())

    for node in yaml_cfg:
        if isinstance(yaml_cfg[node], dict):
            for c in yaml_cfg[node]:
                k = '%s_%s' % (node, c)
                config[k] = yaml_cfg[node][c]
        else:
            config[node] = yaml_cfg[node]
    return config


def load_src(arduino_src):
    lines = []

    with open(arduino_src) as src:
        for l in src:
            lines.append(l)

    return lines


def write_to(build_file, lines):
    pass


def set_src(key, value, lines):
    p = re.compile('(changeme).*// %s$' % key)

    for i, line in enumerate(lines):
        r = p.search(line)
        if r:
            if type(value) is list:
                s = ''
                for v in value:
                    s += ', ' + str(v)
                s = '%s' % (s[2:])
                l = line.replace('changeme', s)
            else:
                l = line.replace('changeme', str(value))

            lines[i] = l
            return lines

    return False

if __name__ == '__main__':
    src = load_src('src/collector.ino')
    config = load_cfg('config/default.yaml')

    for k, v in config.items():
        src = set_src(k, v, src)
        if not src:
            print('failed !', k, v)
            exit(1)

    with open('_build/collector.ino', 'w') as f:
        f.writelines(src)
    subprocess.check_call(['make', 'upload'], cwd='_build')
