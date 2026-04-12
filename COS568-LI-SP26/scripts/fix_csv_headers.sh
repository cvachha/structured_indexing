#!/bin/bash
# Quick fix for CSV headers - run this if you already have results but headers are wrong

echo "Fixing CSV headers in ./results/..."

for FILE in ./results/*mix*.csv
do
    if [ -f "$FILE" ]; then
        echo "Processing $(basename $FILE)..."
        
        # Remove existing header if present
        if head -n 1 "$FILE" | grep -q "index_name"; then
            sed -i '1d' "$FILE"
            echo "  - Removed old header"
        fi
        
        # Add corrected header with flush_threshold column
        sed -i '1s/^/index_name,build_time_ns1,build_time_ns2,build_time_ns3,index_size_bytes,mixed_throughput_mops1,mixed_throughput_mops2,mixed_throughput_mops3,search_method,pgm_error,flush_threshold\n/' "$FILE"
        echo "  - Added new header"
    fi
done

echo ""
echo "Done! Now run: python3 scripts/generate_milestone_report.py"
